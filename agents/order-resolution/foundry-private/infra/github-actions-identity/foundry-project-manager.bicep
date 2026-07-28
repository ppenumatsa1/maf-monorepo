targetScope = 'resourceGroup'

@description('Object ID of the protected private-release service principal.')
param deploymentPrincipalId string

@description('Foundry account that hosts the protected private release project.')
param foundryAccountName string = 'mafprv0722v3ai4aiw7fw5gjdo4'

@description('Foundry project that receives the hosted-agent deployment role.')
param foundryProjectName string = 'order-resolution'

var foundryProjectManagerRoleDefinitionId = 'eadc314b-1a2d-4efa-be10-5d325db5065e'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource foundryProjectManagerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, deploymentPrincipalId, foundryProjectManagerRoleDefinitionId)
  scope: foundryProject
  properties: {
    principalId: deploymentPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryProjectManagerRoleDefinitionId)
  }
}
