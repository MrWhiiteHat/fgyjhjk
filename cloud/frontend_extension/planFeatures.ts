export type PlanTier = "Free" | "Pro" | "Team" | "Enterprise";

export type PlanFeatures = {
  priority_jobs: boolean;
  advanced_reports: boolean;
  dedicated_deployment: boolean;
  sso: boolean;
  scim: boolean;
};

const featureMap: Record<PlanTier, PlanFeatures> = {
  Free: {
    priority_jobs: false,
    advanced_reports: false,
    dedicated_deployment: false,
    sso: false,
    scim: false,
  },
  Pro: {
    priority_jobs: true,
    advanced_reports: true,
    dedicated_deployment: false,
    sso: false,
    scim: false,
  },
  Team: {
    priority_jobs: true,
    advanced_reports: true,
    dedicated_deployment: false,
    sso: true,
    scim: false,
  },
  Enterprise: {
    priority_jobs: true,
    advanced_reports: true,
    dedicated_deployment: true,
    sso: true,
    scim: true,
  },
};

export function featuresForPlan(plan: PlanTier): PlanFeatures {
  return featureMap[plan];
}
