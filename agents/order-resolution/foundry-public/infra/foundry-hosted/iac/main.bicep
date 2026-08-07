targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Public Foundry project name')
param foundryProjectName string = 'order-resolution-public-managed-dev2'

@description('Hosted agent name used to compose the Responses endpoint')
param hostedAgentName string = 'order-resolution-hosted'

@description('Public Foundry account name')
param foundryAccountName string = 'maffndaibfscpfhjr7sp4'

@description('Public Azure Container Registry name')
param containerRegistryName string = 'maffndacrbfscpfhjr7sp4'

@description('Public Container Apps environment name')
param containerAppsEnvironmentName string = 'ora-public-dev2-aca'

@description('Public internal backend Container App name')
param backendContainerAppName string = 'ora-public-dev2-backend'

@description('Public external frontend Container App name')
param frontendContainerAppName string = 'ora-public-dev2-frontend'

@description('Backend bootstrap or azd-published container image')
param backendImageName string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Frontend bootstrap or azd-published container image')
param frontendImageName string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Application Insights component name')
param applicationInsightsName string = 'maffnd-mon-bfscpfhjr7sp4-appi'

@description('Existing Foundry chat deployment name')
param foundryChatDeploymentName string = 'gpt-4o-mini'

@description('Existing Foundry embeddings deployment name')
param foundryEmbeddingsDeploymentName string = 'text-embedding-3-small'

@description('Existing Foundry evaluator deployment name')
param foundryEvaluationDeploymentName string = 'gpt-4o-mini-evaluation'

@secure()
@description('TLS-enabled connection string for the existing workflow PostgreSQL database')
param runtimeDatabaseUrl string = ''

var foundryProjectEndpoint = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
var foundryHostedResponsesUrl = '${foundryProjectEndpoint}/agents/${hostedAgentName}/endpoint/protocols/openai/responses?api-version=v1'

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource acrPullRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  scope: resourceGroup()
}

resource azureAIUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  scope: resourceGroup()
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryChatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' existing = {
  parent: foundryAccount
  name: foundryChatDeploymentName
}

resource foundryEmbeddingsDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' existing = {
  parent: foundryAccount
  name: foundryEmbeddingsDeploymentName
}

resource foundryEvaluationDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' existing = {
  parent: foundryAccount
  name: foundryEvaluationDeploymentName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerAppsRegistryPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${containerAppsEnvironmentName}-acr-pull'
  location: location
}

resource containerAppsRegistryPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, containerAppsRegistryPullIdentity.id, acrPullRole.id)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: containerAppsRegistryPullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendContainerAppName
  location: location
  tags: {
    'azd-service-name': 'backend'
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${containerAppsRegistryPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: containerAppsRegistryPullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          value: runtimeDatabaseUrl
        }
        {
          name: 'application-insights-connection-string'
          value: applicationInsights.properties.ConnectionString
        }
      ]
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImageName
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APP_ENV'
              value: 'aca-public'
            }
            {
              name: 'STORE_PROVIDER'
              value: 'postgres'
            }
            {
              name: 'RUNTIME_TARGET'
              value: 'responses_wrapper'
            }
            {
              name: 'FOUNDRY_RESPONSES_ENDPOINT'
              value: foundryHostedResponsesUrl
            }
            {
              name: 'AZURE_TOKEN_CREDENTIALS'
              value: 'prod'
            }
            {
              name: 'FOUNDRY_PROJECTS_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME'
              value: foundryChatDeploymentName
            }
            {
              name: 'FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME'
              value: foundryEmbeddingsDeploymentName
            }
            {
              name: 'ENABLE_TELEMETRY'
              value: 'true'
            }
            {
              name: 'ENABLE_INSTRUMENTATION'
              value: 'true'
            }
            {
              name: 'OTEL_SERVICE_NAME'
              value: 'maf-order-resolution-aca-backend'
            }
            {
              name: 'OTEL_SERVICE_NAMESPACE'
              value: 'maf-order-resolution'
            }
            {
              name: 'OTEL_RECORD_CONTENT'
              value: 'false'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'application-insights-connection-string'
            }
            {
              name: 'APPINSIGHTS_CONNECTION_STRING'
              secretRef: 'application-insights-connection-string'
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        // The public bootstrap image does not implement the application health contract.
        // HTTP ingress activates the real revision after `azd deploy` replaces it.
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
  dependsOn: [
    containerAppsRegistryPullRoleAssignment
  ]
}

resource frontendContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendContainerAppName
  location: location
  tags: {
    'azd-service-name': 'frontend'
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${containerAppsRegistryPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: containerAppsRegistryPullIdentity.id
        }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5173
        transport: 'http'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImageName
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'API_BASE'
              value: ''
            }
            {
              name: 'NGINX_API_UPSTREAM'
              value: 'https://${backendContainerApp.properties.configuration.ingress.fqdn}'
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 15
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        // The public bootstrap image does not implement the application health contract.
        // HTTP ingress activates the real revision after `azd deploy` replaces it.
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
  dependsOn: [
    containerAppsRegistryPullRoleAssignment
  ]
}

resource backendContainerAppAzureAIUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, backendContainerApp.id, azureAIUserRole.id)
  scope: foundryProject
  properties: {
    roleDefinitionId: azureAIUserRole.id
    principalId: backendContainerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = foundryProjectEndpoint
output FOUNDRY_PROJECTS_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_PROJECT_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_PROJECT_ID string = foundryProject.id
output AZURE_AI_PROJECT_ENDPOINT string = foundryProjectEndpoint
output AZURE_AI_PROJECT_ID string = foundryProject.id
output foundryHostedResponsesUrl string = foundryHostedResponsesUrl
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundryChatDeployment.name
output FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME string = foundryEmbeddingsDeployment.name
output FOUNDRY_EVAL_MODEL string = foundryEvaluationDeployment.name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output APPINSIGHTS_RESOURCE_ID string = applicationInsights.id
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output SERVICE_BACKEND_NAME string = backendContainerApp.name
output SERVICE_BACKEND_IMAGE_NAME string = backendImageName
output SERVICE_BACKEND_URI string = 'https://${backendContainerApp.properties.configuration.ingress.fqdn}'
output SERVICE_BACKEND_ENDPOINTS array = [
  'https://${backendContainerApp.properties.configuration.ingress.fqdn}'
]
output SERVICE_BACKEND_IDENTITY_PRINCIPAL_ID string = backendContainerApp.identity.principalId
output SERVICE_FRONTEND_NAME string = frontendContainerApp.name
output SERVICE_FRONTEND_IMAGE_NAME string = frontendImageName
output SERVICE_FRONTEND_URI string = 'https://${frontendContainerApp.properties.configuration.ingress.fqdn}'
output SERVICE_FRONTEND_ENDPOINTS array = [
  'https://${frontendContainerApp.properties.configuration.ingress.fqdn}'
]
output SERVICE_FRONTEND_IDENTITY_PRINCIPAL_ID string = frontendContainerApp.identity.principalId
output API_BASE_URL string = 'https://${backendContainerApp.properties.configuration.ingress.fqdn}'
output WEB_URL string = 'https://${frontendContainerApp.properties.configuration.ingress.fqdn}'
output requiredBackendSettings array = [
  'FOUNDRY_PROJECTS_ENDPOINT=${foundryProjectEndpoint}'
]
output nextStep string = 'Run the local public release script, then verify hosted Responses conversations and Application Insights telemetry.'
