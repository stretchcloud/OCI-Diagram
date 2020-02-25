from diagrams.oci.compute import Container
from diagrams.oci.devops import Apiservice
from diagrams.oci.network import Firewall
from diagrams.oci.network import Internetgateway
from diagrams.oci.network import Loadbalance
from diagrams.oci.edge import Dns
from diagrams.oci.edge import Waf

from diagrams.oci.connectivity import Customerdatacenter
from diagrams.oci.connectivity import Fastconnect
from diagrams.oci.connectivity import Vpn
from diagrams.oci.network import Drg

from diagrams.oci.monitoring import Alarm
from diagrams.oci.monitoring import Event
from diagrams.oci.monitoring import Logging
from diagrams.oci.monitoring import Telemetry

from diagrams.oci.security import IdAccess

from diagrams import Cluster, Diagram


with Diagram("API Gateway Reference Architecture", show=False):

    dns = Dns("DNS")
    waf = Waf("WAF")
    dc = Customerdatacenter("Customer DC")
    fc = Fastconnect("Fast Connect")
    vpn = Vpn("VPN")
    
    
    with Cluster("Tenancy"):
        ten_grp = [Alarm("Alarm"), 
                   Event("Event"), 
                   Logging("Logging"), 
                   Telemetry("Monitoring")]
        with Cluster("Compartment"):
            id = IdAccess("IAM")
            with Cluster("VCN"):
                ig = Internetgateway("Internet Gateway")
                lb = Loadbalance("Load Balancer")
                api = Apiservice("API Gateway")
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
    
    
    

