# OCI API Gateway Reference Architecture Diagram

Diagrams lets you draw the cloud system architecture **in Python code**.

It was born for **prototyping** a new system architecture without any design tools. You can also describe or visualize the existing system architecture as well.

`Diagram as Code` allows you to **tracking** the architecture diagram changes on any **version control** system.



In this example, we will draw an Oracle Cloud Infrastructure API Gateway Reference Architecture, which is pretty similar to this [one](https://github.com/stretchcloud/OCI-APIGW-Demo-API).



![api_gateway_reference_architecture](https://github.com/stretchcloud/OCI-Diagram/blob/master/api_gateway_reference_architecture.png)





## 1. Clone the repository & install the Python Module



It uses [Graphviz](https://www.graphviz.org/) to render the diagram, so you need to [install Graphviz](https://graphviz.gitlab.io/download/) to use **diagrams**. After installing graphviz (or already have it), install the **diagrams**.



macOS users can download the Graphviz via `brew install graphviz` if you're using [Homebrew](https://brew.sh/). Similarly, Windows users with [Chocolatey](https://chocolatey.org/) installed can run `choco install graphviz`.



Linux users can download the Graphviz from [here](https://graphviz.gitlab.io/download/) and then install it according to your OS flavour.



Clone the Git repo and then install the python module

```bash
$ git clone https://github.com/stretchcloud/OCI-Diagram
$ cd OCI-Diagram
$ pip3 install diagrams
```



Once your installation is done, you are pretty much free to call the Python code which is here. This will generate a nice looking OCI API Gateway Reference Architecture.



```bash
$ python3 OCI-API_GW.py
```



You can extend it for any other purposes as well. [Diagram](https://diagrams.mingrammer.com/) has a list of `oci` modules that you can use to render the diagram. You can get to list all of them [here](https://diagrams.mingrammer.com/docs/nodes/oci). 

