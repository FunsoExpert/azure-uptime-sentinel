# Uptime Sentinel

A serverless website uptime and SSL-expiry monitor on Azure. A timer-triggered Python Azure Function probes a list of URLs every minute, records status, latency and certificate days remaining, and ships structured logs to Application Insights / Log Analytics for querying and alerting. The whole environment is deployed with Bicep.

## Features

- **HTTP health checks**: status code and response latency for each target URL
- **SSL certificate expiry**: days remaining on each HTTPS endpoint, with a warning under 15 days
- **Status classification**: `UP` (2xx/3xx), `DEGRADED` (4xx/5xx), `DOWN` (timeout or connection failure)
- **Structured logs**: consistent `CHECK_RESULT`, `CHECK_FAILURE` and `SSL_*` messages that are easy to query with KQL
- **Config-driven targets**: URLs are passed in as a Bicep parameter and exposed to the function as an app setting
- **Infrastructure as code**: one Bicep template provisions everything

## Architecture

```
Timer trigger (every 60s)
        │
        ▼
Azure Function (Python 3.11, Linux Consumption)
        │   requests + ssl (standard library)
        ▼
Target URLs  ──►  status, latency, cert expiry
        │
        ▼
Application Insights ──► Log Analytics workspace ──► KQL queries / alerts
```

**Azure resources deployed by `main.bicep`:**

| Resource | Purpose |
| --- | --- |
| Storage account | Function runtime storage and content share |
| App Service plan (Y1, Linux) | Consumption hosting |
| Function App | Runs the probe, system-assigned managed identity |
| Application Insights | Telemetry from the function |
| Log Analytics workspace | Backing store for Application Insights |

## Repository structure

```
azure-uptime-sentinel/
├── infrastructure/
│   ├── main.bicep          # All Azure resources
│   └── parameters.json     # Target URLs
├── src/
│   ├── function_app.py     # Timer-triggered probe
│   ├── host.json
│   └── requirements.txt
└── .github/workflows/
    └── deploy.yml          # CI/CD template (placeholder)
```

## Prerequisites

- An Azure subscription
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) with Bicep (`az bicep install`)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- Python 3.11

## Deploy

**1. Sign in and create a resource group**

```powershell
az login
az group create --name rg-uptime-sentinel-lab --location northeurope
```

**2. Deploy the infrastructure**

```powershell
az deployment group create `
    --resource-group rg-uptime-sentinel-lab `
    --template-file infrastructure/main.bicep `
    --parameters infrastructure/parameters.json `
    --output table
```

**3. Publish the function code** (run from `src/`, where `host.json` lives)

```powershell
cd src
func azure functionapp publish uptimesentinel-func --python
cd ..
```

The first cold start can take a few minutes. Telemetry then takes a few more to appear in Application Insights.

## Configuration

Targets are set in `infrastructure/parameters.json`:

```json
{
  "parameters": {
    "targetUrls": {
      "value": [
        "https://microsoft.com",
        "https://httpbin.org/status/200"
      ]
    }
  }
}
```

The Bicep template joins them into the `TARGET_URLS` app setting as a comma-separated list. To change targets without redeploying infrastructure, edit that app setting on the Function App directly.

## Querying results

Run these in Application Insights → **Logs**.

**Latest checks**

```kusto
traces
| where timestamp > ago(1h)
| where message has "CHECK_RESULT" or message has "CHECK_FAILURE" or message has "SSL_"
| project timestamp, message
| order by timestamp desc
```

**Anything not UP**

```kusto
traces
| where timestamp > ago(24h)
| where message has "CHECK_FAILURE" or message has "Status: DEGRADED"
| project timestamp, message
| order by timestamp desc
```

**Certificates close to expiry**

```kusto
traces
| where timestamp > ago(1h)
| where message has "SSL_WARNING"
| project timestamp, message
| order by timestamp desc
```

Example log line:

```
CHECK_RESULT | URL: https://microsoft.com | Status: UP | Code: 200 | Latency: 101ms | SSL Days: 61
```

## Lessons learned

- **Never leave connection-string placeholders in app settings.** An empty `AccountName=;AccountKey=;` string fails deployment with `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING has an invalid value`. Build it from the real storage account with `listKeys()` instead.
- **App settings belong in `siteConfig.appSettings`.** A `sites/config` resource named `web` configures site settings, not app settings.
- **Storage account names are global.** Use `uniqueString(resourceGroup().id)` to avoid collisions.
- **Prefer the standard library for simple jobs.** The cryptography package's certificate API changed between versions. Python's `ssl.getpeercert()` and `ssl.cert_time_to_seconds()` give the expiry date with no extra dependency.
- **Check the exit code before declaring success.** A deployment script that prints "complete" regardless of failure hides real errors.

## Roadmap

- [ ] Azure Monitor alert rules for `DOWN` and `DEGRADED` results
- [ ] Switch `AzureWebJobsStorage` to identity-based access (no account keys)
- [ ] Store results as custom metrics for dashboards
- [ ] Working GitHub Actions pipeline using OIDC login and the Functions deploy action
- [ ] Unit tests for the status classification and expiry logic

## Cost

Runs on the Consumption plan, so you pay per execution plus storage and log ingestion. At one run per minute this is normally small, but check the Azure pricing calculator and set a budget alert on the resource group.

## Cleanup

```powershell
az group delete --name rg-uptime-sentinel-lab --yes --no-wait
```
