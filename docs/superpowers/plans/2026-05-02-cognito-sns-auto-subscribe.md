# Cognito SNS Auto-Subscribe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-subscribe a confirmed Cognito user's email to the `invoice-notifications` SNS topic via a Post Confirmation Lambda trigger.

**Architecture:** A new Lambda `cognito_post_confirm.py` is invoked by Cognito after `PostConfirmation_ConfirmSignUp`. It calls `sns.subscribe()` for the user's email. Errors are caught and logged — the Lambda always returns `event` so user registration is never blocked.

**Tech Stack:** Python 3.12, boto3, moto[sns] for tests, GitHub Actions for CI/CD deploy.

---

## File Map

| File | Action |
|------|--------|
| `invoice-digitizer/backend/lambda/cognito_post_confirm.py` | Create |
| `invoice-digitizer/backend/tests/test_cognito_post_confirm.py` | Create |
| `invoice-digitizer/.github/workflows/backend-ci.yml` | Modify (2 changes) |

---

### Task 1: Write failing tests (TDD RED)

**Files:**
- Create: `invoice-digitizer/backend/tests/test_cognito_post_confirm.py`

- [ ] **Step 1: Create the test file**

```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

os.environ.setdefault('SNS_TOPIC_ARN',
                      'arn:aws:sns:us-east-1:123456789012:invoice-notifications')
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')

import boto3
import pytest
from moto import mock_aws

from cognito_post_confirm import lambda_handler

TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def build_event(trigger_source='PostConfirmation_ConfirmSignUp',
                email='user@example.com'):
    return {
        'triggerSource': trigger_source,
        'request': {
            'userAttributes': {'email': email, 'sub': 'user-uuid-123'}
        }
    }


@mock_aws
def test_confirm_signup_subscribes_email():
    boto3.client('sns', region_name='us-east-1').create_topic(
        Name='invoice-notifications')

    event = build_event()
    result = lambda_handler(event, {})

    subs = boto3.client('sns', region_name='us-east-1') \
        .list_subscriptions_by_topic(TopicArn=TOPIC_ARN)['Subscriptions']

    assert result == event
    assert any(s['Endpoint'] == 'user@example.com' for s in subs)


@mock_aws
def test_forgot_password_does_not_subscribe():
    sns = boto3.client('sns', region_name='us-east-1')
    sns.create_topic(Name='invoice-notifications')

    event = build_event(trigger_source='PostConfirmation_ConfirmForgotPassword')
    result = lambda_handler(event, {})

    subs = sns.list_subscriptions_by_topic(TopicArn=TOPIC_ARN)['Subscriptions']

    assert result == event
    assert subs == []


@mock_aws
def test_missing_email_does_not_raise():
    boto3.client('sns', region_name='us-east-1').create_topic(
        Name='invoice-notifications')

    event = {
        'triggerSource': 'PostConfirmation_ConfirmSignUp',
        'request': {'userAttributes': {'sub': 'user-uuid-123'}}
    }
    result = lambda_handler(event, {})

    assert result == event


@mock_aws
def test_sns_failure_does_not_raise():
    # Topic deliberately not created → sns.subscribe raises NoSuchEntityException
    event = build_event()
    result = lambda_handler(event, {})

    assert result == event
```

- [ ] **Step 2: Run tests — expect ImportError (module not yet created)**

```bash
cd c:/Users/biomig.cali/Documents/AWS_Proyectos_AI/aws-labs-portfolio
pytest invoice-digitizer/backend/tests/test_cognito_post_confirm.py -v
```

Expected output contains:
```
ModuleNotFoundError: No module named 'cognito_post_confirm'
```

- [ ] **Step 3: Commit RED tests**

```bash
git add invoice-digitizer/backend/tests/test_cognito_post_confirm.py
git commit -m "test: RED — cognito post-confirmation SNS subscribe"
```

---

### Task 2: Implement the Lambda (TDD GREEN)

**Files:**
- Create: `invoice-digitizer/backend/lambda/cognito_post_confirm.py`

- [ ] **Step 1: Create the Lambda handler**

```python
import boto3
import os

sns          = boto3.client('sns', region_name='us-east-1')
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

- [ ] **Step 2: Run tests — expect all 4 GREEN**

```bash
pytest invoice-digitizer/backend/tests/test_cognito_post_confirm.py -v
```

Expected output:
```
test_cognito_post_confirm.py::test_confirm_signup_subscribes_email PASSED
test_cognito_post_confirm.py::test_forgot_password_does_not_subscribe PASSED
test_cognito_post_confirm.py::test_missing_email_does_not_raise PASSED
test_cognito_post_confirm.py::test_sns_failure_does_not_raise PASSED
4 passed
```

- [ ] **Step 3: Run full test suite — verify no regressions**

```bash
pytest invoice-digitizer/backend/tests/ -v
```

Expected: all existing tests still pass.

- [ ] **Step 4: Run lint**

```bash
flake8 invoice-digitizer/backend/lambda/cognito_post_confirm.py --max-line-length=100 --ignore=E501,W503,E221,E241
```

Expected: no output (zero errors).

- [ ] **Step 5: Commit GREEN implementation**

```bash
git add invoice-digitizer/backend/lambda/cognito_post_confirm.py
git commit -m "feat: cognito post-confirmation Lambda — auto-subscribe email to SNS"
```

---

### Task 3: Update CI/CD pipeline

**Files:**
- Modify: `invoice-digitizer/.github/workflows/backend-ci.yml`

Two changes needed:
1. Add `sns` to the moto extras on line 20 so the new tests run in CI
2. Add a deploy step for the new Lambda at the end of the deploy job

- [ ] **Step 1: Update moto extras (line 20)**

Current line 20:
```yaml
      - name: Instalar dependencias
        run: pip install pytest boto3 moto[s3,dynamodb] flake8
```

Replace with:
```yaml
      - name: Instalar dependencias
        run: pip install pytest boto3 "moto[s3,dynamodb,sns]" flake8
```

Note the quotes around `moto[s3,dynamodb,sns]` — required in bash to prevent glob expansion of `[`.

- [ ] **Step 2: Add deploy step at end of deploy job**

After the last `Deploy get-invoices` step (currently the final step), append:

```yaml
      - name: Deploy cognito-post-confirm
        run: |
          cd invoice-digitizer/backend/lambda && zip cognito_post_confirm.zip cognito_post_confirm.py
          aws lambda update-function-code --function-name cognito-post-confirm --zip-file fileb://cognito_post_confirm.zip
```

The complete file after both changes:

```yaml
name: Backend CI — Lambda tests + deploy

on:
  push:
    branches: [main]
    paths: ['invoice-digitizer/backend/**', 'invoice-digitizer/infra/**']
  pull_request:
    branches: [main]
    paths: ['invoice-digitizer/backend/**', 'invoice-digitizer/infra/**']

jobs:
  test:
    name: Tests + policy validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Instalar dependencias
        run: pip install pytest boto3 "moto[s3,dynamodb,sns]" flake8
      - name: Lint
        run: flake8 invoice-digitizer/backend/lambda/ --max-line-length=100 --ignore=E501,W503,E221,E241
      - name: Tests
        run: pytest invoice-digitizer/backend/tests/ -v
        env:
          AWS_DEFAULT_REGION: us-east-1
          AWS_ACCESS_KEY_ID: test
          AWS_SECRET_ACCESS_KEY: test

  deploy:
    name: Deploy Lambdas
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Deploy get-upload-url
        run: |
          cd invoice-digitizer/backend/lambda && zip get_upload_url.zip get_upload_url.py
          aws lambda update-function-code --function-name invoice-get-upload-url --zip-file fileb://get_upload_url.zip
      - name: Deploy ocr-processor
        run: |
          cd invoice-digitizer/backend/lambda
          pip install anthropic -t ./pkg/ --quiet
          cd pkg && zip -r ../invoice_ocr_v2.zip . && cd ..
          zip invoice_ocr_v2.zip invoice_ocr_v2.py
          aws lambda update-function-code --function-name invoice-ocr-processor --zip-file fileb://invoice_ocr_v2.zip
          rm -rf pkg invoice_ocr_v2.zip
      - name: Deploy get-invoices
        run: |
          cd invoice-digitizer/backend/lambda && zip get_invoices.zip get_invoices.py
          aws lambda update-function-code --function-name invoice-get-invoices --zip-file fileb://get_invoices.zip
      - name: Deploy cognito-post-confirm
        run: |
          cd invoice-digitizer/backend/lambda && zip cognito_post_confirm.zip cognito_post_confirm.py
          aws lambda update-function-code --function-name cognito-post-confirm --zip-file fileb://cognito_post_confirm.zip
```

- [ ] **Step 3: Verify lint still passes on updated CI file (no Python files touched, just YAML — skip)**

- [ ] **Step 4: Commit CI update**

```bash
git add invoice-digitizer/.github/workflows/backend-ci.yml
git commit -m "feat: add cognito-post-confirm deploy step to CI; add SNS to moto extras"
```

---

## Post-Deploy Manual Steps (AWS Console)

These steps must be done manually after the code lands on `main` and CI deploys the Lambda:

1. **Lambda Console → `cognito-post-confirm` → Configuration → Environment variables**
   - Add: `SNS_TOPIC_ARN` = `<ARN of your invoice-notifications topic>`

2. **IAM Console → Roles → `cognito-post-confirm` execution role → Add inline policy**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": "sns:Subscribe",
       "Resource": "<ARN of invoice-notifications topic>"
     }]
   }
   ```

3. **Cognito Console → User Pools → [your pool] → User pool properties → Add Lambda trigger**
   - Trigger type: **Post confirmation**
   - Lambda: `cognito-post-confirm`
   - Save

4. **Verify:** Register a new test user → confirm account → check email for SNS subscription confirmation link → click it → trigger an OCR invoice → verify notification email arrives.
