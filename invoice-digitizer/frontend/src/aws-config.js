// Valores que completas después de crear los servicios en AWS:
// userPoolId        → Cognito → User Pools → tu pool → Pool ID
// userPoolClientId  → Cognito → App clients → tu client → Client ID
// endpoint          → API Gateway → Stages → prod → Invoke URL

const awsConfig = {
  Auth: {
    Cognito: {
      region:           'us-east-1',
      userPoolId:       process.env.REACT_APP_USER_POOL_ID       || 'us-east-1_XXXXXXXXX',
      userPoolClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID || 'XXXXXXXXXXXXXXXXXXXXXXXXXX',
    }
  },
  API: {
    REST: {
      InvoiceAPI: {
        endpoint: process.env.REACT_APP_API_ENDPOINT || 'https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/prod',
        region: 'us-east-1',
      }
    }
  }
};

export default awsConfig;