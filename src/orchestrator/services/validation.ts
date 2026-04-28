import { ICPDefinition } from '../types/campaign';

export class ValidationError extends Error {
  constructor(public field: string, message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export function validateICP(icp: unknown): asserts icp is ICPDefinition {
  if (!icp || typeof icp !== 'object') {
    throw new ValidationError('icp', 'ICP definition is required');
  }

  const obj = icp as Record<string, unknown>;

  if (!obj.industry || typeof obj.industry !== 'string') {
    throw new ValidationError('icp.industry', 'Industry is required and must be a string');
  }

  if (!obj.companySize || typeof obj.companySize !== 'string') {
    throw new ValidationError('icp.companySize', 'Company size is required');
  }

  if (!obj.region || typeof obj.region !== 'string') {
    throw new ValidationError('icp.region', 'Region is required');
  }

  if (!Array.isArray(obj.titles) || obj.titles.length === 0) {
    throw new ValidationError('icp.titles', 'At least one target title is required');
  }

  if (!Array.isArray(obj.keywords) || obj.keywords.length === 0) {
    throw new ValidationError('icp.keywords', 'At least one keyword is required');
  }
}

export function validateCampaignName(name: unknown): asserts name is string {
  if (!name || typeof name !== 'string' || name.trim().length < 3) {
    throw new ValidationError('name', 'Campaign name must be at least 3 characters');
  }
}
