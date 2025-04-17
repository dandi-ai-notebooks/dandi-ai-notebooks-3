export interface Metadata {
  dandiset_id: string;
  model: string;
  prompt: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_vision_prompt_tokens: number;
  total_vision_completion_tokens: number;
  elapsed_time_seconds: number;
  timestamp: string;
  system_info: {
    platform: string;
    hostname: string;
    processor: string;
    python_version: string;
  };
  subfolder: string;
}

export interface CritiqueManifest {
  files: string[];
  file_count: number;
}
