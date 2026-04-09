// aws-config.js 
const awsConfig = {
  Auth: {
    Cognito: {
      region: 'us-east-1',
      userPoolId: 'us-east-1_mCuzTN6UV', // ID de tu User Pool
      userPoolClientId: '6pff2kis3a7strfph3snjnapjd', // App Client ID
    }
  },
  API: {
    REST: {
      InvoiceAPI: {
        endpoint: 'https://sl2rrcev1b.execute-api.us-east-1.amazonaws.com/prod', // Tu API URL
        region: 'us-east-1',
      }
    }
  }
};

export default awsConfig;
