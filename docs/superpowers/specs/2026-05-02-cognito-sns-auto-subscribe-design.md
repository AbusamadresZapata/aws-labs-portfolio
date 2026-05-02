# Cognito SNS Auto-Subscribe Design

## Goal

Automatically subscribe a new user's email to the existing SNS topic `invoice-notifications` when they confirm their Cognito account, eliminating the current manual subscription step.

## Architecture

A new Lambda `cognito-post-confirm` is triggered by Cognito's **Post Confirmation** event. It reads the email from the event payload and calls `sns.subscribe()` on the existing topic. The trigger fires exactly once per confirmed registration. No new AWS services are introduced — only a new Lambda and one IAM policy.

```
Cognito Confirm → Post Confirmation trigger → cognito-post-confirm Lambda → SNS.subscribe(email)
```

## Files

| File | Action |
|------|--------|
| `invoice-digitizer/backend/lambda/cognito_post_confirm.py` | Create — new Lambda handler |
| `invoice-digitizer/backend/tests/test_cognito_post_confirm.py` | Create — unit tests |
| `invoice-digitizer/.github/workflows/backend-ci.yml` | Modify — add deploy step for new Lambda |

No schema changes. No DynamoDB changes. No frontend changes.

## Lambda Code

```python
import boto3
import os

sns = boto3.client('sns', region_name='us-east-1')
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):
    if event.get('triggerSource') != 'PostConfirmation_ConfirmSignUp':
        return event

    email = event.get('request', {}).get('userAttributes', {}).get('email', '')
    if not email:
        print('WARNING: PostConfirmation event missing email — skipping SNS subscribe')
        return event

    try:
        sns.subscribe(TopicArn=SNS_TOPIC_ARN, Protocol='email', Endpoint=email)
        print(f'INFO: SNS subscribe queued for {email}')
    except Exception as e:
        print(f'ERROR: sns.subscribe failed for {email}: {e}')

    return event
```

## Error Handling

**Critical constraint:** The Lambda must always `return event`. Any unhandled exception blocks the user's registration permanently. Strategy:

- Wrong `triggerSource` → return immediately (covers password reset confirmations)
- Missing `email` → log warning, return event
- `sns.subscribe()` exception → log error, return event (user registers successfully; worst case: no email notifications)

SNS is idempotent: subscribing the same email twice returns the existing subscription ARN without creating duplicates.

## Testing

Four scenarios, one test per behavior:

| Test | Verifies |
|------|----------|
| `ConfirmSignUp` + valid email | `sns.subscribe()` called once; event returned |
| `ConfirmForgotPassword` | `sns.subscribe()` NOT called; event returned |
| Missing email in userAttributes | No exception raised; event returned |
| `sns.subscribe()` raises exception | No exception propagated; event returned |

Tool: `pytest` + `moto[sns]`. TDD: RED first, then implementation.

## Environment Variables

| Lambda | Variable | Value |
|--------|----------|-------|
| `cognito-post-confirm` | `SNS_TOPIC_ARN` | ARN of existing `invoice-notifications` topic |

## IAM Policy (attach to Lambda execution role)

```json
{
  "Effect": "Allow",
  "Action": "sns:Subscribe",
  "Resource": "<ARN of invoice-notifications topic>"
}
```

## Manual Steps in AWS Console

1. **Deploy Lambda** — CI/CD handles this after merge to `main`
2. **Set `SNS_TOPIC_ARN` env var** — in Lambda Console → Configuration → Environment variables
3. **Attach IAM policy** — add `sns:Subscribe` permission to the Lambda's execution role
4. **Connect Cognito trigger** — Cognito Console → User Pool → User pool properties → Add Lambda trigger → Post confirmation → select `cognito-post-confirm`

## Out of Scope

- Migration of existing users (only new registrations are covered)
- Tracking subscription ARNs in DynamoDB
- Unsubscribe flow
