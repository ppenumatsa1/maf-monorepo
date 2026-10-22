targetScope = 'resourceGroup'

@description('Name of the Microsoft Foundry resource that hosts the deployed agent.')
@minLength(2)
@maxLength(64)
param foundryResourceName string

@description('Name of the Microsoft Foundry project that contains the deployed agent.')
@minLength(1)
@maxLength(64)
param foundryProjectName string

@description('Name of the deployed hosted agent.')
@minLength(1)
@maxLength(64)
param hostedAgentName string

@description('Client ID of the active hosted-agent identity.')
@minLength(36)
@maxLength(36)
param agentIdentityClientId string

@description('Microsoft Entra tenant ID for the hosted-agent identity.')
@minLength(36)
@maxLength(36)
param tenantId string

@description('Resource ID of the Log Analytics workspace that receives Azure Bot diagnostics.')
@minLength(1)
param logAnalyticsWorkspaceResourceId string

@description('Globally unique Azure Bot Service resource name.')
@minLength(2)
@maxLength(64)
param botName string

@description('Display name for the Azure Bot Service resource.')
@minLength(1)
@maxLength(128)
param botDisplayName string = hostedAgentName

@description('Azure Bot Service SKU supplied by the external deployment profile.')
@allowed([
  'F0'
  'S1'
])
param botSkuName string

var validatedFoundryResourceName = !contains(foundryResourceName, '/') && !contains(foundryResourceName, ' ') && !contains(foundryResourceName, '?') && !contains(foundryResourceName, '#')
  ? foundryResourceName
  : fail('foundryResourceName must be safe for use as an Azure AI Services hostname.')
var validatedFoundryProjectName = !contains(foundryProjectName, '/') && !contains(foundryProjectName, ' ') && !contains(foundryProjectName, '?') && !contains(foundryProjectName, '#')
  ? foundryProjectName
  : fail('foundryProjectName must be safe for use as an Activity endpoint path segment.')
var validatedHostedAgentName = !contains(hostedAgentName, '/') && !contains(hostedAgentName, ' ') && !contains(hostedAgentName, '?') && !contains(hostedAgentName, '#')
  ? hostedAgentName
  : fail('hostedAgentName must be safe for use as an Activity endpoint path segment.')
var validatedAgentIdentityClientId = substring(agentIdentityClientId, 8, 1) == '-' && substring(agentIdentityClientId, 13, 1) == '-' && substring(agentIdentityClientId, 18, 1) == '-' && substring(agentIdentityClientId, 23, 1) == '-'
  ? agentIdentityClientId
  : fail('agentIdentityClientId must have GUID shape.')
var validatedTenantId = substring(tenantId, 8, 1) == '-' && substring(tenantId, 13, 1) == '-' && substring(tenantId, 18, 1) == '-' && substring(tenantId, 23, 1) == '-'
  ? tenantId
  : fail('tenantId must have GUID shape.')
var validatedLogAnalyticsWorkspaceResourceId = startsWith(toLower(logAnalyticsWorkspaceResourceId), '/subscriptions/') && contains(toLower(logAnalyticsWorkspaceResourceId), '/providers/microsoft.operationalinsights/workspaces/')
  ? logAnalyticsWorkspaceResourceId
  : fail('logAnalyticsWorkspaceResourceId must identify a Microsoft.OperationalInsights workspace.')

var activityProtocolApiVersion = '2025-05-15-preview'
var activityEndpoint = 'https://${validatedFoundryResourceName}.services.ai.azure.com/api/projects/${validatedFoundryProjectName}/agents/${validatedHostedAgentName}/endpoint/protocols/activityProtocol?api-version=${activityProtocolApiVersion}'

resource botService 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botName
  kind: 'azurebot'
  location: 'global'
  sku: {
    name: botSkuName
  }
  properties: {
    displayName: botDisplayName
    endpoint: activityEndpoint
    msaAppId: validatedAgentIdentityClientId
    msaAppTenantId: validatedTenantId
    msaAppType: 'SingleTenant'
    publicNetworkAccess: 'Enabled'
  }
}

resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: botService
  name: 'MsTeamsChannel'
  location: 'global'
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      acceptedTerms: true
      deploymentEnvironment: 'CommercialDeployment'
      enableCalling: false
      isEnabled: true
    }
  }
}

resource botDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'bot-request-diagnostics'
  scope: botService
  properties: {
    workspaceId: validatedLogAnalyticsWorkspaceResourceId
    logs: [
      {
        category: 'BotRequest'
        enabled: true
        retentionPolicy: {
          days: 0
          enabled: false
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          days: 0
          enabled: false
        }
      }
    ]
  }
}

output botResourceId string = botService.id
output botName string = botService.name
output teamsChannelResourceId string = teamsChannel.id
output teamsChannelName string = teamsChannel.name
output botDiagnosticSettingResourceId string = botDiagnostics.id
output activityEndpoint string = activityEndpoint
