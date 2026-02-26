// ---------------------------------------------------------------------------
// Module: foundry-project.bicep
// Deploys a Foundry project as a child of the existing AIServices resource.
// The project inherits all model deployments from the parent — no
// duplication needed.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

// ---------------------------------------------------------------------------
// Foundry Project (child of AIServices)
// ---------------------------------------------------------------------------
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: 'ai-${baseName}'
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServicesAccount
  name: 'proj-${baseName}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'KB Agent Foundry project'
    displayName: 'KB Agent (proj-${baseName})'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output projectName string = project.name
output projectEndpoint string = project.properties.endpoints['AI Foundry API']
