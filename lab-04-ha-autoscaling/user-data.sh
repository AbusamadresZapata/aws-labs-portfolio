#!/bin/bash
# 1. Actualización e instalación silenciosa
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd

# 2. Obtener metadatos con IMDSv2 (Seguro y moderno)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/local-ipv4)

# 3. Crear la página con estilo visual AWS
cat <<EOF > /var/www/html/index.html
<!DOCTYPE html>
<html>
<head>
    <title>AWS Lab 04 - Alta Disponibilidad</title>
    <style>
        body { font-family: 'Open Sans', sans-serif; background: #232F3E; color: white; text-align: center; padding-top: 100px; }
        .container { background: white; color: #232F3E; display: inline-block; padding: 40px; border-radius: 10px; border-top: 10px solid #FF9900; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .tag { background: #FF9900; color: white; padding: 5px 15px; border-radius: 5px; font-weight: bold; }
        h1 { margin-top: 0; }
        hr { border: 0; border-top: 1px solid #ddd; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AWS Lab 04: Alta Disponibilidad</h1>
        <p>Ingeniero: <strong>Juan Sebastian Arrechea</strong></p>
        <hr>
        <p>Atendido desde la Zona: <span class="tag">$AZ</span></p>
        <p>ID de Instancia: <strong>$INSTANCE_ID</strong></p>
        <p>IP Privada: <strong>$PRIVATE_IP</strong></p>
        <p style="font-size: 0.8em; color: #888;">Auto-escalado y Balanceo funcionando correctamente</p>
    </div>
</body>
</html>
EOF