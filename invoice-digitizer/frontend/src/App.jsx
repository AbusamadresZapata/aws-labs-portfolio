import { Amplify } from 'aws-amplify';
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import awsConfig from './aws-config';
import Dashboard from './pages/Dashboard';

Amplify.configure(awsConfig);

function AppContent() {
  const { user, signOut } = useAuthenticator();
  return <Dashboard user={user} onSignOut={signOut} />;
}

export default function App() {
  return (
    <Authenticator
      signUpAttributes={['email']}
      loginMechanisms={['email']}
      components={{
        Header() {
          return (
            <div style={{ textAlign: 'center', padding: '2rem 1rem 0' }}>
              <h1 style={{ fontSize: 22, fontWeight: 500, marginBottom: 4 }}>
                Digitalizador de Recibos
              </h1>
              <p style={{ fontSize: 13, color: '#666', marginBottom: '1.5rem' }}>
                Sube una foto de tu recibo y extrae los datos automáticamente
              </p>
            </div>
          );
        }
      }}
    >
      <AppContent />
    </Authenticator>
  );
}