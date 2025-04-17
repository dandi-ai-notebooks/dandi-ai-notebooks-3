import { useMemo, useState } from 'react';
import { Metadata, NotebookRankingsData } from './types';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  FormControl,
  Select,
  MenuItem,
  InputLabel,
  TableSortLabel,
  Typography,
  Link
} from '@mui/material';

type SortKey = keyof Metadata | 'rank' | 'est_cost';

type SortConfig = {
  key: SortKey;
  direction: 'asc' | 'desc';
};

interface Props {
  notebooks: Metadata[];
  critiques: Set<string>;
  notebookRankings: NotebookRankingsData;
}

export default function NotebooksTable({ notebooks, critiques, notebookRankings }: Props) {
  const [selectedDandiset, setSelectedDandiset] = useState<string>('');
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: 'timestamp' as SortKey,
    direction: 'desc'
  });

  const uniqueDandisets = useMemo(() => {
    const dandisets = [...new Set(notebooks.map(n => n.dandiset_id))];
    return dandisets.sort();
  }, [notebooks]);

  const handleSort = (key: SortKey) => {
    const direction = sortConfig.key === key && sortConfig.direction === 'asc' ? 'desc' : 'asc';
    setSortConfig({ key, direction });
  };

  const getNotebookRanking = useMemo(() => ((notebook: Metadata) => {
    const dandisetRankings = notebookRankings[notebook.dandiset_id];
    if (!dandisetRankings) return null;

    return dandisetRankings.rankings.find(r => r.notebook_id === notebook.subfolder);
  }), [notebookRankings]);

  const getPromptUrl = (prompt: string) => {
    return `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-2/blob/main/templates/${prompt}.txt`;
  };

  const getRankingsUrl = (notebook: Metadata) => {
    return `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/rankings/dandisets/${notebook.dandiset_id}/rankings.txt`;
  };

  const getCritiqueUrls = (notebook: Metadata) => {
    const basePath = `dandisets/${notebook.dandiset_id}/${notebook.subfolder}`;
    const cellsPath = `${basePath}/cells_critique.txt`;
    const summaryPath = `${basePath}/summary_critique.txt`;

    return {
      cells: critiques.has(cellsPath) ?
        `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/critiques/${cellsPath}` :
        null,
      summary: critiques.has(summaryPath) ?
        `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/critiques/${summaryPath}` :
        null
    };
  };

  const filteredAndSortedNotebooks = useMemo(() => {
    const filtered = selectedDandiset
      ? notebooks.filter(n => n.dandiset_id === selectedDandiset)
      : notebooks;


    return [...filtered].sort((a, b) => {
      if (sortConfig.key === 'rank') {
        const aRanking = getNotebookRanking(a)?.rank ?? Number.MAX_SAFE_INTEGER;
        const bRanking = getNotebookRanking(b)?.rank ?? Number.MAX_SAFE_INTEGER;
        return sortConfig.direction === 'asc'
          ? aRanking - bRanking
          : bRanking - aRanking;
      }

      let aValue = a[sortConfig.key as keyof Metadata];
      let bValue = b[sortConfig.key as keyof Metadata];

      if (sortConfig.key === 'model') {
        aValue = (aValue as string).split('/')[1] || '';
        bValue = (bValue as string).split('/')[1] || '';
      }

      if (sortConfig.key === 'est_cost') {
        aValue = calculateEstimatedCost(a) || 0;
        bValue = calculateEstimatedCost(b) || 0;
      }

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortConfig.direction === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortConfig.direction === 'asc'
          ? aValue - bValue
          : bValue - aValue;
      }

      return 0;
    });
  }, [notebooks, sortConfig, selectedDandiset, getNotebookRanking]);

  return (
    <div>
      <Typography variant="h4" gutterBottom>
        DANDI AI Notebooks Explorer
      </Typography>

      <FormControl sx={{ minWidth: 200, mb: 2 }}>
        <InputLabel id="dandiset-select-label">Filter by Dandiset ID</InputLabel>
        <Select
          labelId="dandiset-select-label"
          value={selectedDandiset}
          label="Filter by Dandiset ID"
          onChange={(e) => setSelectedDandiset(e.target.value)}
        >
          <MenuItem value="">
            <em>All Dandisets</em>
          </MenuItem>
          {uniqueDandisets.map((id) => (
            <MenuItem key={id} value={id}>{id}</MenuItem>
          ))}
        </Select>
      </FormControl>

      <TableContainer component={Paper}>
        <Table sx={{ minWidth: 650 }}>
          <TableHead>
            <TableRow>
              <TableCell>Notebook</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'subfolder'}
                  direction={sortConfig.key === 'subfolder' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('subfolder')}
                >
                  Subfolder
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'dandiset_id'}
                  direction={sortConfig.key === 'dandiset_id' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('dandiset_id')}
                >
                  Dandiset
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'model'}
                  direction={sortConfig.key === 'model' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('model')}
                >
                  Model
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'prompt'}
                  direction={sortConfig.key === 'prompt' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('prompt')}
                >
                  Prompt
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'est_cost'}
                  direction={sortConfig.key === 'est_cost' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('est_cost')}
                >
                  Est. Cost ($)
                </TableSortLabel>
              </TableCell>
              <TableCell>Critiques</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'rank'}
                  direction={sortConfig.key === 'rank' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('rank')}
                >
                  Ranking
                </TableSortLabel>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAndSortedNotebooks.map((notebook, index) => {
              const critiqueUrls = getCritiqueUrls(notebook);
              return (
                <TableRow key={index}>
                  <TableCell>
                    <Link
                      href={`https://github.com/dandi-ai-notebooks/${notebook.dandiset_id}/blob/main/${notebook.subfolder}/${notebook.dandiset_id}.ipynb`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {notebook.dandiset_id}.ipynb
                    </Link>
                  </TableCell>
                  <TableCell>{notebook.subfolder}</TableCell>
                  <TableCell>{notebook.dandiset_id}</TableCell>
                  <TableCell>
                    {notebook.model.split('/')[1] || notebook.model}
                  </TableCell>
                  <TableCell>
                    <Link
                      href={getPromptUrl(notebook.prompt)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {notebook.prompt}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {calculateEstimatedCost(notebook)?.toFixed(2) || 'N/A'}
                  </TableCell>
                  <TableCell>
                    {critiqueUrls.cells && (
                      <Link
                        href={critiqueUrls.cells}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ mr: 2 }}
                      >
                        Cells
                      </Link>
                    )}
                    {critiqueUrls.summary && (
                      <Link
                        href={critiqueUrls.summary}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Summary
                      </Link>
                    )}
                  </TableCell>
                  <TableCell>
                    {(() => {
                      const ranking = getNotebookRanking(notebook);
                      if (!ranking) return null;
                      return (
                        <Link
                          href={getRankingsUrl(notebook)}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={ranking.thinking}
                          sx={{ cursor: 'pointer' }}
                        >
                          {ranking.rank}
                        </Link>
                      );
                    })()}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  );
}

const calculateEstimatedCost = (metadata: Metadata) => {
  const getModelCost = (model: string): [number | undefined, number | undefined] => {
    if (model === 'google/gemini-2.0-flash-001') return [0.1, 0.4];
    else if (model === 'openai/gpt-4o') return [2.5, 10];
    else if (model === 'anthropic/claude-3.5-sonnet') return [3, 15];
    else if (model === 'anthropic/claude-3.7-sonnet') return [3, 15];
    else if (model === 'anthropic/claude-3.7-sonnet:thinking') return [3, 15];
    else if (model === 'deepseek/deepseek-r1') return [0.55, 2.19];
    else if (model === 'deepseek/deepseek-chat-v3-0324') return [0.27, 1.1];
    else if (model === 'openai/o4-mini') return [1.1, 4.4];
    else if (model === 'openai/o4-mini-high') return [1.1, 4.4];
    else if (model === 'openai/o3') return [10, 40];
    return [undefined, undefined];
  };

  if (!metadata) return 0;

  const [promptCost, completionCost] = getModelCost(metadata.model);
  if (promptCost === undefined || completionCost === undefined) return undefined;
  if (!metadata) return undefined;
  const totalPromptTokens = (metadata.total_prompt_tokens || 0) + (metadata.total_vision_prompt_tokens || 0);
  const totalCompletionTokens = (metadata.total_completion_tokens || 0) + (metadata.total_vision_completion_tokens || 0);

  return ((totalPromptTokens / 1e6 * promptCost) + (totalCompletionTokens / 1e6 * completionCost));
};