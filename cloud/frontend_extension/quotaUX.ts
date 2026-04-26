export type QuotaStatus = {
  used: number;
  soft_limit: number;
  hard_limit: number;
  soft_warning: boolean;
  hard_block: boolean;
};

export function quotaLabel(status: QuotaStatus): string {
  if (status.hard_block) {
    return "Limit exceeded";
  }
  if (status.soft_warning) {
    return "Approaching limit";
  }
  return "Within quota";
}

export function quotaProgress(status: QuotaStatus): number {
  if (status.hard_limit <= 0) {
    return 0;
  }
  return Math.min(1, status.used / status.hard_limit);
}
