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

export interface Grade {
  question_id: string;
  grade: number;
  thinking: string;
}

export interface NotebookGradings {
  prompt_version: string;
  grades: Grade[];
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

export type NotebookGradingsData = {
  dandiset_id: string;
  subfolder: string;
  gradings: NotebookGradings;
}[];

export type ReviewResultType = {
  type: "qualification_test";
  model: string;
  dandiset_id: string;
  subfolder: string;
  passing: boolean;
} | {
  type: "comparison";
  model: string;
  dandiset_id: string;
  subfolder1: string;
  subfolder2: string;
  selection: number;
} | {
  type: "rankings";
  model: string;
  dandiset_id: string;
  notebooks: {
    subfolder: string;
    wins: number;
    losses: number;
  }[];
};

export interface ReviewResults {
  results: ReviewResultType[];
}
