from diagrams import Cluster, Diagram
from diagrams.aws.compute import EC2
from diagrams.aws.network import VPC, PublicSubnet, PrivateSubnet, InternetGateway

with Diagram("lab-02-serverless-api", show=False):
    igw = InternetGateway("igw")

    with Cluster("VPC (10.0.0.0/16)"):
        with Cluster("Public Subnet"):
            web_server = EC2("Apache Web Server")
            igw >> web_server

        with Cluster("Private Subnet"):
            db_server = EC2("Internal DB")
            web_server >> db_server # Representando la conexión interna