export interface User {
  id: string;
  email: string;
  is_verified: boolean;
  balance: number;
}

export interface Dataset {
  id: string;
  name: string;
  filename: string;
  format: string;
  size_bytes: number;
  row_count: number | null;
  validation_status: string;
  validation_errors: string[];
  created_at: string;
}

export interface Job {
  id: string;
  dataset_id: string;
  base_model_id: string;
  preset: string;
  adapter: string;
  status: string;
  status_detail: string | null;
  estimated_cost: number | null;
  actual_cost: number | null;
  progress_pct: number;
  error_message: string | null;
  ogpu_task_address: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BaseModel {
  id: string;
  name: string;
  param_count: number;
  min_vram_gb: number;
  supported_adapters: string[];
}

export interface Presets {
  [key: string]: {
    label: string;
    description: string;
    epochs: number;
    learning_rate: number;
  };
}

export interface ModelsResponse {
  models: BaseModel[];
  presets: Presets;
}

export interface BalanceResponse {
  balance: number;
  currency: string;
}
