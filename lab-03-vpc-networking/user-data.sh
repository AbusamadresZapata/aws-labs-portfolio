#!/bin/bash
# Actualizar el sistema
yum update -y

# Instalar Apache (httpd)
yum install -y httpd

# Iniciar y habilitar el servicio
systemctl start httpd
systemctl enable httpd

# Crear una página de bienvenida personalizada para el Lab 03
echo "<h1>Lab 03: VPC Networking & Security</h1>" > /var/www/html/index.html
echo "<p>Desplegado por: Juan Sebastian Arrechea</p>" >> /var/www/html/index.html
echo "<p>Servidor Apache funcionando en subred publica.</p>" >> /var/www/html/index.html
