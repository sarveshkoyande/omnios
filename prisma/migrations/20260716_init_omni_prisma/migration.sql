-- Migration generated from prisma/schema.prisma
-- Target: PostgreSQL

CREATE TYPE "ClaimType" AS ENUM (
  'efficacy',
  'safety',
  'rtb',
  'isi',
  'fair_balance',
  'moa',
  'access',
  'other'
);

CREATE TYPE "ClaimStatus" AS ENUM (
  'draft',
  'in_review',
  'approved',
  'expired',
  'retired'
);

CREATE TYPE "CampaignStatus" AS ENUM (
  'draft',
  'in_review',
  'approved',
  'live',
  'closed'
);

CREATE TYPE "ReviewAction" AS ENUM (
  'submitted',
  'approved',
  'rejected',
  'expired',
  'withdrawn'
);

CREATE TYPE "LifecycleKey" AS ENUM (
  'launch',
  'growth',
  'mature',
  'loe'
);

CREATE TYPE "HcpChannelPreferenceType" AS ENUM (
  'PREFERRED',
  'TOLERATED',
  'AVOIDED'
);

CREATE TABLE "Client" (
    "id" SERIAL PRIMARY KEY,
    "name" TEXT NOT NULL UNIQUE
);

CREATE TABLE "Brand" (
    "id" SERIAL PRIMARY KEY,
    "clientId" INTEGER,
    "name" TEXT NOT NULL UNIQUE,
    "genericName" TEXT,
    "therapyArea" TEXT,
    "lifecycleKey" "LifecycleKey",

    CONSTRAINT "Brand_clientId_fkey"
      FOREIGN KEY ("clientId") REFERENCES "Client"("id")
);

CREATE TABLE "Indication" (
    "id" SERIAL PRIMARY KEY,
    "brandId" INTEGER NOT NULL,
    "label" TEXT NOT NULL,

    CONSTRAINT "Indication_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id") ON DELETE CASCADE,

    CONSTRAINT "Indication_brandId_label_key"
      UNIQUE ("brandId", "label")
);

CREATE TABLE "TaxonomyTerm" (
    "id" SERIAL PRIMARY KEY,
    "dimension" TEXT NOT NULL,
    "term" TEXT NOT NULL,

    CONSTRAINT "TaxonomyTerm_dimension_term_key"
      UNIQUE ("dimension", "term")
);

CREATE TABLE "Blob" (
    "blobKey" TEXT PRIMARY KEY,
    "mimeType" TEXT,
    "byteSize" INTEGER,
    "originalName" TEXT,
    "storageUri" TEXT NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE "RefSource" (
    "id" SERIAL PRIMARY KEY,
    "sourceType" TEXT NOT NULL,
    "citation" TEXT NOT NULL,
    "url" TEXT,
    "externalId" TEXT,
    "annotation" TEXT,
    "blobKey" TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "RefSource_blobKey_fkey"
      FOREIGN KEY ("blobKey") REFERENCES "Blob"("blobKey"),

    CONSTRAINT "RefSource_sourceType_externalId_key"
      UNIQUE ("sourceType", "externalId")
);

CREATE TABLE "Claim" (
    "id" SERIAL PRIMARY KEY,
    "brandId" INTEGER,
    "indicationId" INTEGER,
    "text" TEXT NOT NULL,
    "claimType" "ClaimType" NOT NULL DEFAULT 'efficacy',
    "claimStatus" "ClaimStatus" NOT NULL DEFAULT 'draft',
    "materialNumber" TEXT,
    "mlrCode" TEXT,
    "approvedAt" TIMESTAMPTZ,
    "expiresAt" TIMESTAMPTZ,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "Claim_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id"),

    CONSTRAINT "Claim_indicationId_fkey"
      FOREIGN KEY ("indicationId") REFERENCES "Indication"("id"),

    CONSTRAINT "Claim_materialNumber_key"
      UNIQUE ("materialNumber")
);

CREATE TABLE "ClaimReference" (
    "claimId" INTEGER NOT NULL,
    "refId" INTEGER NOT NULL,
    "locator" TEXT,

    CONSTRAINT "ClaimReference_pkey"
      PRIMARY KEY ("claimId", "refId"),

    CONSTRAINT "ClaimReference_claimId_fkey"
      FOREIGN KEY ("claimId") REFERENCES "Claim"("id") ON DELETE CASCADE,

    CONSTRAINT "ClaimReference_refId_fkey"
      FOREIGN KEY ("refId") REFERENCES "RefSource"("id") ON DELETE CASCADE
);

CREATE TABLE "ContentModule" (
    "id" SERIAL PRIMARY KEY,
    "brandId" INTEGER,
    "indicationId" INTEGER,
    "name" TEXT NOT NULL,
    "moduleType" TEXT NOT NULL DEFAULT 'text',
    "status" TEXT NOT NULL DEFAULT 'draft',
    "materialNumber" TEXT,
    "businessRules" TEXT,
    "blobKey" TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "ContentModule_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id"),

    CONSTRAINT "ContentModule_indicationId_fkey"
      FOREIGN KEY ("indicationId") REFERENCES "Indication"("id"),

    CONSTRAINT "ContentModule_blobKey_fkey"
      FOREIGN KEY ("blobKey") REFERENCES "Blob"("blobKey"),

    CONSTRAINT "ContentModule_materialNumber_key"
      UNIQUE ("materialNumber")
);

CREATE TABLE "ModuleClaim" (
    "moduleId" INTEGER NOT NULL,
    "claimId" INTEGER NOT NULL,

    CONSTRAINT "ModuleClaim_pkey"
      PRIMARY KEY ("moduleId", "claimId"),

    CONSTRAINT "ModuleClaim_moduleId_fkey"
      FOREIGN KEY ("moduleId") REFERENCES "ContentModule"("id") ON DELETE CASCADE,

    CONSTRAINT "ModuleClaim_claimId_fkey"
      FOREIGN KEY ("claimId") REFERENCES "Claim"("id") ON DELETE CASCADE
);

CREATE TABLE "ContentAsset" (
    "id" SERIAL PRIMARY KEY,
    "brandId" INTEGER,
    "indicationId" INTEGER,
    "fileName" TEXT,
    "title" TEXT,
    "assetFormat" TEXT,
    "branded" BOOLEAN,
    "targetGroup" TEXT,
    "description" TEXT,
    "url" TEXT,
    "idCode" TEXT,
    "blobKey" TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "ContentAsset_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id"),

    CONSTRAINT "ContentAsset_indicationId_fkey"
      FOREIGN KEY ("indicationId") REFERENCES "Indication"("id"),

    CONSTRAINT "ContentAsset_blobKey_fkey"
      FOREIGN KEY ("blobKey") REFERENCES "Blob"("blobKey")
);

CREATE TABLE "AssetModule" (
    "assetId" INTEGER NOT NULL,
    "moduleId" INTEGER NOT NULL,

    CONSTRAINT "AssetModule_pkey"
      PRIMARY KEY ("assetId", "moduleId"),

    CONSTRAINT "AssetModule_assetId_fkey"
      FOREIGN KEY ("assetId") REFERENCES "ContentAsset"("id") ON DELETE CASCADE,

    CONSTRAINT "AssetModule_moduleId_fkey"
      FOREIGN KEY ("moduleId") REFERENCES "ContentModule"("id") ON DELETE CASCADE
);

CREATE TABLE "EntityTag" (
    "entityKind" TEXT NOT NULL,
    "entityId" INTEGER NOT NULL,
    "termId" INTEGER NOT NULL,

    CONSTRAINT "EntityTag_pkey"
      PRIMARY KEY ("entityKind", "entityId", "termId"),

    CONSTRAINT "EntityTag_termId_fkey"
      FOREIGN KEY ("termId") REFERENCES "TaxonomyTerm"("id") ON DELETE CASCADE
);

CREATE TABLE "Campaign" (
    "id" SERIAL PRIMARY KEY,
    "projectId" TEXT,
    "brandId" INTEGER,
    "indicationId" INTEGER,
    "name" TEXT NOT NULL,
    "lifecycleKey" "LifecycleKey",
    "persona" TEXT,
    "journeyStage" TEXT,
    "cxMaturity" TEXT,
    "objective" TEXT,
    "totalBudget" DOUBLE PRECISION,
    "status" "CampaignStatus" NOT NULL DEFAULT 'draft',
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "Campaign_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id"),

    CONSTRAINT "Campaign_indicationId_fkey"
      FOREIGN KEY ("indicationId") REFERENCES "Indication"("id")
);

CREATE TABLE "CampaignVersion" (
    "id" SERIAL PRIMARY KEY,
    "campaignId" INTEGER NOT NULL,
    "versionNo" INTEGER NOT NULL,
    "planBlobKey" TEXT,
    "resultBlobKey" TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "CampaignVersion_campaignId_fkey"
      FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE,

    CONSTRAINT "CampaignVersion_planBlobKey_fkey"
      FOREIGN KEY ("planBlobKey") REFERENCES "Blob"("blobKey"),

    CONSTRAINT "CampaignVersion_resultBlobKey_fkey"
      FOREIGN KEY ("resultBlobKey") REFERENCES "Blob"("blobKey"),

    CONSTRAINT "CampaignVersion_campaignId_versionNo_key"
      UNIQUE ("campaignId", "versionNo")
);

CREATE TABLE "CampaignSegment" (
    "id" SERIAL PRIMARY KEY,
    "campaignId" INTEGER NOT NULL,
    "persona" TEXT,
    "abcdJson" JSONB,
    "ladderJson" JSONB,
    "digitalJson" JSONB,

    CONSTRAINT "CampaignSegment_campaignId_fkey"
      FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE
);

CREATE TABLE "CampaignMessage" (
    "id" SERIAL PRIMARY KEY,
    "campaignId" INTEGER NOT NULL,
    "topic" TEXT NOT NULL,
    "ord" INTEGER,
    "claimId" INTEGER,

    CONSTRAINT "CampaignMessage_campaignId_fkey"
      FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE,

    CONSTRAINT "CampaignMessage_claimId_fkey"
      FOREIGN KEY ("claimId") REFERENCES "Claim"("id")
);

CREATE TABLE "CampaignChannel" (
    "id" SERIAL PRIMARY KEY,
    "campaignId" INTEGER NOT NULL,
    "channel" TEXT NOT NULL,
    "sharePct" DOUBLE PRECISION,
    "budgetAmount" DOUBLE PRECISION,
    "ppNpp" TEXT,

    CONSTRAINT "CampaignChannel_campaignId_fkey"
      FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE
);

CREATE TABLE "CampaignKpi" (
    "id" SERIAL PRIMARY KEY,
    "campaignId" INTEGER NOT NULL,
    "kpiType" TEXT,
    "metric" TEXT NOT NULL,

    CONSTRAINT "CampaignKpi_campaignId_fkey"
      FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE
);

CREATE TABLE "ReviewRecord" (
    "id" SERIAL PRIMARY KEY,
    "entityKind" TEXT NOT NULL,
    "entityId" INTEGER NOT NULL,
    "action" "ReviewAction" NOT NULL,
    "reviewer" TEXT,
    "decisionAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "notes" TEXT
);

CREATE TABLE "BrandMarketIntel" (
    "id" SERIAL PRIMARY KEY,
    "brandId" INTEGER,
    "brandName" TEXT NOT NULL UNIQUE,
    "lifecycleStage" "LifecycleKey" NOT NULL,
    "stageConfidence" TEXT,
    "momentum" TEXT,
    "evidenceJson" JSONB,
    "catalystsJson" JSONB,
    "competitorsJson" JSONB,
    "loeHorizon" TEXT,
    "whitespace" TEXT,
    "campaignPosture" TEXT,
    "asOf" TIMESTAMPTZ,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT "BrandMarketIntel_brandId_fkey"
      FOREIGN KEY ("brandId") REFERENCES "Brand"("id")
);

CREATE TABLE "CampaignAward" (
    "id" SERIAL PRIMARY KEY,
    "awardId" TEXT NOT NULL UNIQUE,
    "title" TEXT NOT NULL,
    "client" TEXT,
    "brand" TEXT,
    "therapyArea" TEXT,
    "rosterLink" TEXT,
    "rosterLinkNote" TEXT,
    "festival" TEXT,
    "award" TEXT,
    "tier" TEXT,
    "year" INTEGER,
    "agency" TEXT,
    "whyAwarded" TEXT,
    "keyMessage" TEXT,
    "creativeSummary" TEXT,
    "imagesDescription" TEXT,
    "sourceUrlsJson" JSONB,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE "SyntheticHcpPersona" (
    "id" TEXT PRIMARY KEY,
    "name" TEXT NOT NULL,
    "audienceType" TEXT NOT NULL,
    "gender" TEXT,
    "ethnicity" TEXT,
    "segmentKey" TEXT,
    "segmentName" TEXT,
    "specialty" TEXT,
    "condition" TEXT,
    "therapyAreas" JSONB,
    "location" TEXT,
    "setting" TEXT,
    "age" INTEGER,
    "yearsInPractice" INTEGER,
    "tagline" TEXT,
    "bio" TEXT,
    "tone" TEXT,
    "voiceSample" TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE "SyntheticHcpPrescribing" (
    "id" SERIAL PRIMARY KEY,
    "personaId" TEXT NOT NULL UNIQUE,
    "monthlyTrx" INTEGER,
    "monthlyNrx" INTEGER,
    "trxTrend" TEXT,
    "decile" INTEGER,
    "patientVolume" TEXT,
    "adoptionCurve" TEXT,
    "brandStance" TEXT,

    CONSTRAINT "SyntheticHcpPrescribing_personaId_fkey"
      FOREIGN KEY ("personaId") REFERENCES "SyntheticHcpPersona"("id") ON DELETE CASCADE
);

CREATE TABLE "SyntheticHcpDigitalProfile" (
    "id" SERIAL PRIMARY KEY,
    "personaId" TEXT NOT NULL UNIQUE,
    "affinity" TEXT,
    "affinityScore" INTEGER,
    "emailOpen" TEXT,
    "repAccess" TEXT,
    "devices" JSONB,

    CONSTRAINT "SyntheticHcpDigitalProfile_personaId_fkey"
      FOREIGN KEY ("personaId") REFERENCES "SyntheticHcpPersona"("id") ON DELETE CASCADE
);

CREATE TABLE "SyntheticHcpChannelPreference" (
    "id" SERIAL PRIMARY KEY,
    "personaId" TEXT NOT NULL,
    "preferenceType" "HcpChannelPreferenceType" NOT NULL,
    "channel" TEXT NOT NULL,
    "note" TEXT,

    CONSTRAINT "SyntheticHcpChannelPreference_personaId_fkey"
      FOREIGN KEY ("personaId") REFERENCES "SyntheticHcpPersona"("id") ON DELETE CASCADE,

    CONSTRAINT "SyntheticHcpChannelPreference_personaId_preferenceType_channel_key"
      UNIQUE ("personaId", "preferenceType", "channel")
);

CREATE TABLE "SyntheticHcpPersonaTag" (
    "id" SERIAL PRIMARY KEY,
    "personaId" TEXT NOT NULL,
    "tagType" TEXT NOT NULL,
    "value" TEXT NOT NULL,

    CONSTRAINT "SyntheticHcpPersonaTag_personaId_fkey"
      FOREIGN KEY ("personaId") REFERENCES "SyntheticHcpPersona"("id") ON DELETE CASCADE
);

CREATE INDEX "TaxonomyTerm_dimension_idx"
  ON "TaxonomyTerm" ("dimension");

CREATE INDEX "RefSource_sourceType_idx"
  ON "RefSource" ("sourceType");

CREATE INDEX "Claim_brandId_idx"
  ON "Claim" ("brandId");

CREATE INDEX "Claim_claimStatus_idx"
  ON "Claim" ("claimStatus");

CREATE INDEX "ContentModule_brandId_idx"
  ON "ContentModule" ("brandId");

CREATE INDEX "ContentModule_status_idx"
  ON "ContentModule" ("status");

CREATE INDEX "ContentAsset_brandId_idx"
  ON "ContentAsset" ("brandId");

CREATE INDEX "Campaign_brandId_idx"
  ON "Campaign" ("brandId");

CREATE INDEX "ReviewRecord_entityKind_entityId_idx"
  ON "ReviewRecord" ("entityKind", "entityId");

CREATE INDEX "BrandMarketIntel_lifecycleStage_idx"
  ON "BrandMarketIntel" ("lifecycleStage");

CREATE INDEX "CampaignAward_therapyArea_idx"
  ON "CampaignAward" ("therapyArea");

CREATE INDEX "CampaignAward_brand_idx"
  ON "CampaignAward" ("brand");

CREATE INDEX "CampaignAward_client_idx"
  ON "CampaignAward" ("client");

CREATE INDEX "SyntheticHcpChannelPreference_personaId_idx"
  ON "SyntheticHcpChannelPreference" ("personaId");

CREATE INDEX "SyntheticHcpPersonaTag_personaId_tagType_idx"
  ON "SyntheticHcpPersonaTag" ("personaId", "tagType");

-- Reporting view equivalent to the SQLite convenience view.
CREATE VIEW "v_unsubstantiated_claims" AS
SELECT
  c."id",
  c."text",
  c."claimStatus",
  c."brandId"
FROM "Claim" c
LEFT JOIN "ClaimReference" cr ON cr."claimId" = c."id"
WHERE cr."claimId" IS NULL
  AND c."claimStatus" = 'approved';
