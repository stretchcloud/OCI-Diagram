from diagrams import Diagram


from diagrams.oci.connectivity import DNS
from diagrams.oci.security import WAF
from diagrams.oci.connectivity import CustomerDatacenter
from diagrams.oci.connectivity import FastConnect
from diagrams.oci.connectivity import VPN
from diagrams.oci.monitoring import Alarm
from diagrams.oci.monitoring import Events
from diagrams.oci.monitoring import Telemetry
from diagrams.oci.governance import Logging
from diagrams.oci.security import IDAccess
from diagrams.oci.network import InternetGateway
from diagrams.oci.network import LoadBalancer
from diagrams.oci.network import Firewall
from diagrams.oci.devops import APIService
from diagrams.oci.network import Drg
from diagrams.oci.compute import Container


from diagrams import Cluster, Diagram

with Diagram("API Gateway Reference Architecture", show=False):

    dns = DNS("DNS")
    waf = WAF("WAF")
    dc = CustomerDatacenter("Customer DC")
    fc = FastConnect("Fast Connect")
    vpn = VPN("VPN")
    
    
    with Cluster("Tenancy"):
        ten_grp = [Alarm("Alarm"), 
                   Events("Event"), 
                   Logging("Logging"), 
                   Telemetry("Monitoring")]
        with Cluster("Compartment"):
            id = IDAccess("IAM")
            with Cluster("VCN"):
                ig = InternetGateway("Internet Gateway")
                lb = LoadBalancer("Load Balancer")
                api = APIService("API Gateway")
                fw = Firewall("Firewall")
                drg = Drg("DRG")



                with Cluster("OKE Cluster"):

                    oke_grp = [Container("Node01"),
                               Container("Node02"),
                               Container("Node03")]
            oke_grp >> id
            id >> ten_grp    

        
    waf >> dns >> ig >> fw >> api >> lb >> oke_grp
    dc >> fc >> drg
    dc >> vpn >> drg
    drg >> fw >> api