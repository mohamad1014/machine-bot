param location string
param serverName string
param adminLogin string
@secure()
param adminPassword string
param databaseName string

resource server 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: serverName
  location: location
  properties: {
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    version: '12.0'
  }
}

// Allow Azure services to access (typical for quick-start)
resource firewall 'Microsoft.Sql/servers/firewallRules@2022-05-01-preview' = {
  name: 'AllowAzureServices'
  parent: server
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource db 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  name: '${server.name}/${databaseName}'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {}
}

output fqdn string = server.properties.fullyQualifiedDomainName
output connectionString string = 'Server=tcp:${server.properties.fullyQualifiedDomainName},1433;Database=${db.name};Authentication=Active Directory Default;Encrypt=yes;TrustServerCertificate=no;'

