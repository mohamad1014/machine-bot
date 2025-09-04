Infrastructure as Code (Bicep)

This folder contains Bicep templates to provision a Python 3.12 Azure Functions app (v4 runtime, Python v2 programming model) and common dependencies: Storage, Application Insights, Cosmos DB, and Azure SQL.

Prerequisites
- Azure CLI logged in: `az login`
- Bicep (bundled with Azure CLI)
- Resource group created or create one during deployment

Parameters (main.bicep)
- `location`: Azure region (e.g., `westeurope`)
- `namePrefix`: Prefix for resource names (lowercase, letters and digits)
- `cosmosDbName`: Cosmos DB database name
- `cosmosContainerName`: Cosmos DB container name
- `sqlAdminLogin` / `sqlAdminPassword`: SQL admin credentials

Deploy
1) Create resource group (if needed):
   az group create -n rg-machine-bot -l westeurope

2) Deploy:
   az deployment group create \
     -g rg-machine-bot \
     -f infra/main.bicep \
     -p namePrefix=mbot location=westeurope cosmosDbName=db cosmosContainerName=items sqlAdminLogin=sqladmin sqlAdminPassword=YOUR_STRONG_PASSWORD

Outputs include connection values you can set as application settings locally (or wire via Key Vault).

