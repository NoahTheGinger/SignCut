CREATE TABLE "Tools" ("rowId" INTEGER PRIMARY KEY AUTOINCREMENT, "id" TEXT NOT NULL, "toolType" TEXT NOT NULL, "flags" INTEGER NOT NULL, "visibilityFlags" INTEGER NOT NULL, "requirements" BLOB NOT NULL, "authenticationPolicy" TEXT NOT NULL, "customIcon" BLOB, "deprecationReplacementId" TEXT, "sourceActionProvider" TEXT, "outputTypeInstance" BLOB, "sourceContainerId" INTEGER NOT NULL, "attributionContainerId" INTEGER, UNIQUE ("id", "sourceContainerId"), FOREIGN KEY ("sourceContainerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE CASCADE, FOREIGN KEY ("attributionContainerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE SET NULL);

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE "ToolOutputTypes" ("toolId" INTEGER NOT NULL, "typeIdentifier" TEXT NOT NULL, UNIQUE ("toolId", "typeIdentifier"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "SystemToolProtocols" ("toolId" INTEGER NOT NULL, "identifier" TEXT NOT NULL, "protocol" BLOB NOT NULL, FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "ToolLocalizations" ("toolId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, "outputResultName" TEXT, "descriptionSummary" TEXT, "descriptionAttribution" TEXT, "descriptionResult" TEXT, "descriptionNote" TEXT, "descriptionRequires" TEXT, "deprecationMessage" TEXT, "localizationUsage" TEXT NOT NULL, PRIMARY KEY ("toolId", "locale", "localizationUsage"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "Parameters" ("typeInstance" BLOB NOT NULL, "key" TEXT NOT NULL, "sortOrder" INTEGER NOT NULL, "relationships" BLOB NOT NULL, "flags" INTEGER NOT NULL, "toolId" INTEGER NOT NULL, PRIMARY KEY ("toolId", "key"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "ToolParameterTypes" ("toolId" INTEGER NOT NULL, "key" TEXT NOT NULL, "typeId" INTEGER NOT NULL, PRIMARY KEY ("toolId", "key", "typeId"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE, FOREIGN KEY ("toolId", "key") REFERENCES "Parameters"("toolId", "key") ON DELETE CASCADE);

CREATE TABLE "ParameterLocalizations" ("toolId" INTEGER NOT NULL, "key" TEXT NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, "description" TEXT, "trueString" TEXT, "falseString" TEXT, PRIMARY KEY ("toolId", "key", "locale"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE, FOREIGN KEY ("toolId", "key") REFERENCES "Parameters"("toolId", "key") ON DELETE CASCADE);

CREATE TABLE "Categories" ("toolId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "category" TEXT NOT NULL, PRIMARY KEY ("toolId", "category", "locale"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "SearchKeywords" ("toolId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "keyword" TEXT NOT NULL, "order" INTEGER NOT NULL, PRIMARY KEY ("toolId", "locale", "keyword"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "SystemTypeProtocols" ("typeId" INTEGER NOT NULL, "identifier" TEXT NOT NULL, "protocol" BLOB NOT NULL, PRIMARY KEY ("typeId", "protocol"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "TypeCoercions" ("typeId" TEXT NOT NULL, "coercionDefinition" BLOB NOT NULL, FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "UTTypeCoercions" ("typeId" TEXT NOT NULL, "coercionIdentifier" TEXT NOT NULL, PRIMARY KEY ("typeId", "coercionIdentifier"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "Types" ("rowId" TEXT PRIMARY KEY NOT NULL, "id" BLOB NOT NULL, "sourceContainerId" INTEGER NOT NULL, "kind" INTEGER NOT NULL, "runtimeFlags" INTEGER, "runtimeRequirements" BLOB, FOREIGN KEY ("sourceContainerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE CASCADE);

CREATE TABLE "TypeDisplayRepresentations" ("typeId" TEXT NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, "numericFormat" TEXT, "synonyms" BLOB NOT NULL, PRIMARY KEY ("typeId", "locale"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "EntityProperties" ("id" TEXT NOT NULL, "typeId" TEXT NOT NULL, "typeInstance" BLOB NOT NULL, "spotlightAttributeKey" TEXT, "spotlightCustomAttributeKey" TEXT, PRIMARY KEY ("id", "typeId"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "EntityPropertyLocalizations" ("typeId" TEXT NOT NULL, "propertyId" TEXT NOT NULL, "locale" TEXT NOT NULL, "displayName" TEXT NOT NULL, PRIMARY KEY ("propertyId", "locale", "typeId"), FOREIGN KEY ("propertyId", "typeId") REFERENCES "EntityProperties"("id", "typeId") ON DELETE CASCADE);

CREATE TABLE "EnumerationCases" ("typeId" TEXT NOT NULL, "locale" TEXT NOT NULL, "id" TEXT NOT NULL, "title" TEXT, "subtitle" BLOB, "altText" BLOB, "image" BLOB, "snippetPluginModel" BLOB, "synonyms" BLOB NOT NULL, PRIMARY KEY ("typeId", "id", "locale"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "PredicateTemplates" ("typeId" TEXT NOT NULL, "comparison" BLOB NOT NULL, "stringSearch" BLOB, "valueSearch" BLOB, "idSearch" BLOB, "searchableItem" BLOB, "all" BLOB, "unique" BLOB, "valid" BLOB, "suggested" BLOB, "metadata" BLOB, PRIMARY KEY ("typeId"), FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "Metadata" ("key" TEXT PRIMARY KEY NOT NULL, "value" BLOB NOT NULL);

CREATE TABLE "ContainerMetadata" ("rowId" INTEGER PRIMARY KEY AUTOINCREMENT, "id" TEXT NOT NULL, "bundleVersion" TEXT NOT NULL, "teamId" TEXT NOT NULL, "deviceId" TEXT NOT NULL, "origin" INTEGER NOT NULL, "containerType" INTEGER NOT NULL, UNIQUE ("id", "bundleVersion", "deviceId"));

CREATE TABLE "AdditionalToolAttributionContainers" ("toolId" INTEGER NOT NULL, "containerId" TEXT NOT NULL, PRIMARY KEY ("toolId", "containerId"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE, FOREIGN KEY ("containerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE CASCADE);

CREATE TABLE "ContainerMetadataLocalizations" ("containerId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, PRIMARY KEY ("containerId", "locale"), FOREIGN KEY ("containerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE CASCADE);

CREATE TABLE "ContainerMetadataSynonyms" ("containerId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "synonym" TEXT NOT NULL, "order" INTEGER NOT NULL, PRIMARY KEY ("containerId", "locale", "synonym"), FOREIGN KEY ("containerId") REFERENCES "ContainerMetadata"("rowId") ON DELETE CASCADE);

CREATE TABLE "SampleInvocation" ("rowId" INTEGER PRIMARY KEY AUTOINCREMENT, "toolId" INTEGER NOT NULL, "parameterKey" TEXT, "expectedResult" TEXT, FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE, FOREIGN KEY ("toolId", "parameterKey") REFERENCES "Parameters"("toolId", "key") ON DELETE CASCADE);

CREATE TABLE "SampleInvocationPhrase" ("rowId" INTEGER PRIMARY KEY AUTOINCREMENT, "invocationId" INTEGER NOT NULL, "annotation" INTEGER NOT NULL, "phrase" TEXT NOT NULL, FOREIGN KEY ("invocationId") REFERENCES "SampleInvocation"("rowId") ON DELETE CASCADE);

CREATE TABLE "LaunchServicesState" ("bundleId" TEXT PRIMARY KEY NOT NULL, "persistentIdentifier" BLOB NOT NULL);

CREATE TABLE "LinkState" ("containerId" TEXT PRIMARY KEY NOT NULL, "installIdentifier" BLOB NOT NULL);

CREATE TABLE "LinkActionIdentifiers" ("identifier" TEXT NOT NULL, "toolId" INTEGER NOT NULL, UNIQUE ("toolId", "identifier"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE "Triggers" ("rowId" INTEGER PRIMARY KEY AUTOINCREMENT, "id" TEXT NOT NULL, "flags" INTEGER NOT NULL, "requirements" BLOB NOT NULL, "outputTypeInstance" BLOB);

CREATE TABLE "TriggerLocalizations" ("triggerId" INTEGER NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, "outputResultName" TEXT, "descriptionSummary" TEXT, PRIMARY KEY ("triggerId", "locale"), FOREIGN KEY ("triggerId") REFERENCES "Triggers"("rowId") ON DELETE CASCADE);

CREATE TABLE "TriggerParameters" ("typeInstance" BLOB NOT NULL, "key" TEXT NOT NULL, "sortOrder" INTEGER NOT NULL, "relationships" BLOB NOT NULL, "flags" INTEGER NOT NULL, "typeId" TEXT NOT NULL, "triggerId" INTEGER NOT NULL, PRIMARY KEY ("triggerId", "key"), FOREIGN KEY ("triggerId") REFERENCES "Triggers"("rowId") ON DELETE CASCADE, FOREIGN KEY ("typeId") REFERENCES "Types"("rowId") ON DELETE CASCADE);

CREATE TABLE "TriggerParameterLocalizations" ("triggerId" INTEGER NOT NULL, "key" TEXT NOT NULL, "locale" TEXT NOT NULL, "name" TEXT NOT NULL, "description" TEXT, PRIMARY KEY ("triggerId", "key", "locale"), FOREIGN KEY ("triggerId") REFERENCES "Triggers"("rowId") ON DELETE CASCADE, FOREIGN KEY ("triggerId", "key") REFERENCES "TriggerParameters"("triggerId", "key") ON DELETE CASCADE);

CREATE TABLE "TriggerOutputTypes" ("triggerId" INTEGER NOT NULL, "typeIdentifier" TEXT NOT NULL, UNIQUE ("triggerId", "typeIdentifier"), FOREIGN KEY ("triggerId") REFERENCES "Triggers"("rowId") ON DELETE CASCADE);

CREATE TABLE "ToolCascadeSharedIdentifiers" ("toolId" INTEGER NOT NULL, "cascadeSharedIdentifier" TEXT NOT NULL, "deviceId" INTEGER NOT NULL, UNIQUE ("toolId", "cascadeSharedIdentifier", "deviceId"), FOREIGN KEY ("toolId") REFERENCES "Tools"("rowId") ON DELETE CASCADE);

CREATE TABLE sqlite_stat1(tbl,idx,stat);

CREATE INDEX "Tools_on_sourceActionProvider" ON "Tools"("sourceActionProvider");

CREATE INDEX "Tools_on_sourceContainerId" ON "Tools"("sourceContainerId");

CREATE INDEX "Tools_on_attributionContainerId" ON "Tools"("attributionContainerId");

CREATE INDEX "ToolOutputTypes_on_toolId" ON "ToolOutputTypes"("toolId");

CREATE INDEX "ToolOutputTypes_on_typeIdentifier" ON "ToolOutputTypes"("typeIdentifier");

CREATE INDEX "SystemToolProtocols_on_toolId" ON "SystemToolProtocols"("toolId");

CREATE INDEX "SystemToolProtocols_on_identifier" ON "SystemToolProtocols"("identifier");

CREATE INDEX "ToolLocalizations_on_toolId" ON "ToolLocalizations"("toolId");

CREATE INDEX "ToolLocalizations_on_locale" ON "ToolLocalizations"("locale");

CREATE INDEX "ToolLocalizations_on_localizationUsage" ON "ToolLocalizations"("localizationUsage");

CREATE INDEX "ToolParameterTypes_on_toolId" ON "ToolParameterTypes"("toolId");

CREATE INDEX "ToolParameterTypes_on_key" ON "ToolParameterTypes"("key");

CREATE INDEX "ToolParameterTypes_on_typeId" ON "ToolParameterTypes"("typeId");

CREATE INDEX "ParameterLocalizations_on_toolId" ON "ParameterLocalizations"("toolId");

CREATE INDEX "ParameterLocalizations_on_key" ON "ParameterLocalizations"("key");

CREATE INDEX "ParameterLocalizations_on_locale" ON "ParameterLocalizations"("locale");

CREATE INDEX "SystemTypeProtocols_on_typeId" ON "SystemTypeProtocols"("typeId");

CREATE INDEX "SystemTypeProtocols_on_identifier" ON "SystemTypeProtocols"("identifier");

CREATE INDEX "TypeCoercions_on_typeId" ON "TypeCoercions"("typeId");

CREATE INDEX "UTTypeCoercions_on_typeId" ON "UTTypeCoercions"("typeId");

CREATE INDEX "UTTypeCoercions_on_coercionIdentifier" ON "UTTypeCoercions"("coercionIdentifier");

CREATE INDEX "Types_on_id" ON "Types"("id");

CREATE INDEX "Types_on_sourceContainerId" ON "Types"("sourceContainerId");

CREATE INDEX "Types_on_kind" ON "Types"("kind");

CREATE INDEX "EntityProperties_on_typeId" ON "EntityProperties"("typeId");

CREATE INDEX "EnumerationCases_on_locale" ON "EnumerationCases"("locale");

CREATE INDEX "ContainerMetadata_on_id" ON "ContainerMetadata"("id");

CREATE INDEX "ContainerMetadata_on_deviceId" ON "ContainerMetadata"("deviceId");

CREATE INDEX "ContainerMetadata_on_containerType" ON "ContainerMetadata"("containerType");

CREATE INDEX "ContainerMetadata_rowId_deviceId" ON "ContainerMetadata"("rowId", "deviceId");

CREATE INDEX "AdditionalToolAttributionContainers_on_toolId" ON "AdditionalToolAttributionContainers"("toolId");

CREATE INDEX "AdditionalToolAttributionContainers_on_containerId" ON "AdditionalToolAttributionContainers"("containerId");

CREATE INDEX "ContainerMetadataLocalizations_on_containerId" ON "ContainerMetadataLocalizations"("containerId");

CREATE INDEX "ContainerMetadataLocalizations_on_locale" ON "ContainerMetadataLocalizations"("locale");

CREATE INDEX "ContainerMetadataSynonyms_locale_containerId" ON "ContainerMetadataSynonyms"("locale", "containerId");

CREATE INDEX "SampleInvocation_on_toolId" ON "SampleInvocation"("toolId");

CREATE INDEX "SampleInvocation_on_parameterKey" ON "SampleInvocation"("parameterKey");

CREATE INDEX "SampleInvocationPhrase_on_invocationId" ON "SampleInvocationPhrase"("invocationId");

CREATE INDEX "LinkActionIdentifiers_on_identifier" ON "LinkActionIdentifiers"("identifier");

CREATE INDEX "LinkActionIdentifiers_on_toolId" ON "LinkActionIdentifiers"("toolId");

CREATE INDEX "TriggerLocalizations_on_triggerId" ON "TriggerLocalizations"("triggerId");

CREATE INDEX "TriggerLocalizations_on_locale" ON "TriggerLocalizations"("locale");

CREATE INDEX "TriggerParameters_on_typeId" ON "TriggerParameters"("typeId");

CREATE INDEX "TriggerParameterLocalizations_on_triggerId" ON "TriggerParameterLocalizations"("triggerId");

CREATE INDEX "TriggerParameterLocalizations_on_key" ON "TriggerParameterLocalizations"("key");

CREATE INDEX "TriggerParameterLocalizations_on_locale" ON "TriggerParameterLocalizations"("locale");

CREATE INDEX "TriggerOutputTypes_on_triggerId" ON "TriggerOutputTypes"("triggerId");

CREATE INDEX "TriggerOutputTypes_on_typeIdentifier" ON "TriggerOutputTypes"("typeIdentifier");

CREATE INDEX "ToolCascadeSharedIdentifiers_on_cascadeSharedIdentifier" ON "ToolCascadeSharedIdentifiers"("cascadeSharedIdentifier")