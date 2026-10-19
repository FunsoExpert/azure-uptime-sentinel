# Azure Serverless Uptime Sentinel 

An enterprise-grade, serverless website uptime and performance monitoring engine built natively on Azure using Python, Azure Functions, Application Insights, and Bicep Infrastructure as Code (IaC).

##  Architecture Overview
\\\
[Timer Trigger (60s)] ---> [Azure Function App (Python 3.11)]
                                  |
            +---------------------+---------------------+
            | (HTTP Status & Latency)                   | (SSL Expiry Check)
            v                                           v
    [Target Endpoints]                         [Application Insights]
\\\

##  Tech Stack & Services
* **Compute:** Azure Function App (Serverless Consumption Plan, Linux Python 3.11)
* **Monitoring & Telemetry:** Azure Application Insights & Log Analytics Workspace
* **Infrastructure as Code:** Azure Bicep (Atomic inline \siteConfig\ app settings with implicit dependency graphing)
* **Storage:** Azure Storage Account (Standard LRS, TLS 1.2 enforced)

##  Repository Structure
\\`text
azure-uptime-sentinel/
 infrastructure/
    main.bicep              # Complete declarative infrastructure
    parameters.json         # Monitoring endpoints configuration
 src/
    function_app.py         # Timer-triggered Python probe logic
    requirements.txt        # Python package dependencies
    host.json               # Function runtime settings
 README.md
\\`

##  Deployment Guide

1. **Clone the Repository:**
   \\`bash
   git clone https://github.com/YOUR-USERNAME/azure-uptime-sentinel.git
   cd azure-uptime-sentinel
   \\`

2. **Login to Azure CLI:**
   \\`powershell
   az login
   \\`

3. **Deploy Infrastructure via Bicep:**
   \\`powershell
   az group create --name rg-uptime-sentinel-lab --location francecentral
   az deployment group create --resource-group rg-uptime-sentinel-lab --template-file infrastructure\main.bicep --parameters infrastructure\parameters.json
   \\`

4. **Publish Function Code:**
   \\`powershell
   cd src
   func azure functionapp publish uptimesentinel-func --python
   cd ..
   \\`

##  Production Hardening & Design Decisions
* **Race Condition Avoidance:** Leveraged inline siteConfig.appSettings rather than decoupled config resources, allowing ARM to automatically resolve storage account listKeys() dependencies.
* **Global Naming Safety:** Utilized deterministic unique string interpolation (uniqueString) to prevent global Azure Storage account naming collisions.
* **Security Standards:** Enforced TLS 1.2 minimum encryption and HTTPS-only traffic rules across all resources.
