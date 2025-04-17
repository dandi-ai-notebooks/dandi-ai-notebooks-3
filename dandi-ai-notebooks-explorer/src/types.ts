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

export interface NotebookRanking {
  notebook_id: string;
  rank: number;
  thinking: string;
}

export interface DandisetRankings {
  prompt_version: string;
  rankings: NotebookRanking[];
  rankings_text: string;
  metadata: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    model: string;
    timestamp: string;
    system_info: {
      platform: string;
      hostname: string;
    }
  }
}

export interface NotebookRankingsData {
  [dandiset_id: string]: DandisetRankings;
}
