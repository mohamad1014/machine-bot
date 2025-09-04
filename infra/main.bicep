param location string
@minLength(3)
param namePrefix string

@description('Cosmos DB database name')
param cosmosDbName string
@description('Cosmos DB container name')
param cosmosContainerName string

@secure()
@description('SQL admin password (only used to bootstrap)')
param sqlAdminPassword string
@description('SQL admin login name')
param sqlAdminLogin string

var storageAccountName = toLower('${namePrefix}stor${uniqueString(resourceGroup().id)}')
var functionAppName = toLower('${namePrefix}-func-${uniqueString(resourceGroup().id)}')
var appInsightsName = toLower('${namePrefix}-appi')
var planName = toLower('${namePrefix}-plan')
var cosmosAccountName = toLower(replace('${namePrefix}${uniqueString(resourceGroup().id)}','-',''))
var sqlServerName = toLower('${namePrefix}-sql-${uniqueString(resourceGroup().id)}')
var sqlDbName = 'appdb'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: planName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    maximumElasticWorkerCount: 1
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    location: location
    accountName: cosmosAccountName
    databaseName: cosmosDbName
    containerName: cosmosContainerName
  }
}

module sql './modules/sql.bicep' = {
  name: 'sql'
  params: {
    location: location
    serverName: sqlServerName
    adminLogin: sqlAdminLogin
    adminPassword: sqlAdminPassword
    databaseName: sqlDbName
  }
}

resource func 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      ftpsState: 'FtpsOnly'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${listKeys(storage.id, storage.apiVersion).keys[0].value}'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appi.properties.InstrumentationKey
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'CosmosDbConnection'
          value: cosmos.outputs.connectionString
        }
        {
          name: 'CosmosDatabase'
          value: cosmosDbName
        }
        {
          name: 'CosmosContainer'
          value: cosmosContainerName
        }
        {
          name: 'SqlConnectionString'
          value: sql.outputs.connectionString
        }
      ]
    }
  }
}

output functionAppName string = functionAppName
output storageAccountName string = storage.name
output cosmosEndpoint string = cosmos.outputs.endpoint
output cosmosPrimaryKey string = cosmos.outputs.primaryKey
output cosmosConnectionString string = cosmos.outputs.connectionString
output sqlServerFqdn string = sql.outputs.fqdn
output sqlConnectionString string = sql.outputs.connectionString

