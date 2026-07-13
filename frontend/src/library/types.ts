export interface LibraryBrandSummary {
  brand: string;
  generic_name?: string;
  client?: string;
  therapy_area?: string;
  lifecycle_key?: string;
  claims: number;
  approved: number;
  references: number;
  modules: number;
  images: number;
}

export interface LibraryIndex {
  brands: LibraryBrandSummary[];
  totals: {
    claims?: number;
    claims_approved?: number;
    references?: number;
    content_modules?: number;
    content_assets?: number;
    unsubstantiated_claims?: number;
  };
}

export interface ClaimReference {
  source_type: string;
  external_id?: string;
  url?: string;
  citation?: string;
}

export interface Claim {
  id: string;
  claim_type: string;
  status: "approved" | "in_review" | "draft" | string;
  text: string;
  material_number?: string;
  indication?: string;
  expires_at?: string;
  references: ClaimReference[];
}

export interface ContentModule {
  module_type: string;
  status: string;
  material_number?: string;
  name: string;
  business_rules?: string;
  claims: { text: string }[];
}

export interface ContentAsset {
  asset_format: string;
  title: string;
  description?: string;
  branded: boolean;
  id_code?: string;
  blob_key?: string;
}

export interface LabelImage {
  blob_key: string;
  title: string;
  file_name?: string;
  url?: string;
}

export interface LibraryDetail {
  found: boolean;
  brand: string;
  generic?: string;
  client?: string;
  therapy_area?: string;
  indications: string[];
  counts: {
    claims: number;
    approved: number;
    modules: number;
    images: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
  };
  images: LabelImage[];
  claims: Claim[];
  modules: ContentModule[];
  assets: ContentAsset[];
}

export const CLAIM_TYPE_LABEL: Record<string, string> = {
  efficacy: "Efficacy",
  safety: "Safety",
  moa: "Mechanism",
  access: "Access & dosing",
  rtb: "Reason to believe",
  isi: "Important Safety Info",
  fair_balance: "Fair balance",
  other: "Other",
};

export const CLAIM_SRC_LABEL: Record<string, string> = {
  dailymed: "DailyMed label",
  clinicaltrials: "ClinicalTrials.gov",
  pubmed: "PubMed",
  openfda: "openFDA",
  data_on_file: "Data on file",
  congress: "Congress",
  guideline: "Guideline",
};
