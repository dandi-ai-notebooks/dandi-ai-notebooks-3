import { useMemo, useState } from 'react';
import { Metadata } from './types';
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

type SortKey = keyof Metadata | 'est_cost' | 'qual' | 'rank';

type SortConfig = {
  key: SortKey;
  direction: 'asc' | 'desc';
};

interface Props {
  notebooks: Metadata[];
  // critiques: Set<string>;
  // notebookGradings: NotebookGradingsData;
  qualResults: Map<string, boolean>;
  rankResults: Map<string, number>;
  modelForReviews: string;
}

export default function NotebooksTable({ notebooks, qualResults, rankResults, modelForReviews }: Props) {
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

  // const getNotebookGrade = useMemo(() => ((notebook: Metadata) => {
  //   const grading = notebookGradings.find(
  //     g => g.dandiset_id === notebook.dandiset_id && g.subfolder === notebook.subfolder
  //   );
  //   if (!grading) return null;

  //   return {
  //     total: grading.gradings.grades.reduce((sum: number, g: Grade) => sum + g.grade, 0),
  //     thinking: grading.gradings.grades.map((g: Grade) => `${g.question_id} (${g.grade}) ${g.thinking}`).join('\n\n'),
  //     url: `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/gradings2/dandisets/${notebook.dandiset_id}/${notebook.subfolder}/grades.json`
  //   };
  // }), [notebookGradings]);

  const getPromptUrl = (prompt: string) => {
    return `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/templates/${prompt}`;
  };

  // const getCritiqueUrls = (notebook: Metadata) => {
  //   const basePath = `dandisets/${notebook.dandiset_id}/${notebook.subfolder}`;
  //   const cellsPath = `${basePath}/cells_critique.txt`;
  //   const summaryPath = `${basePath}/summary_critique.txt`;

  //   return {
  //     cells: critiques.has(cellsPath) ?
  //       `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/critiques/${cellsPath}` :
  //       null,
  //     summary: critiques.has(summaryPath) ?
  //       `https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/critiques/${summaryPath}` :
  //       null
  //   };
  // };

  const filteredAndSortedNotebooks = useMemo(() => {
    const filtered = selectedDandiset
      ? notebooks.filter(n => n.dandiset_id === selectedDandiset)
      : notebooks;


    return [...filtered].sort((a, b) => {
      // if (sortConfig.key === 'grade') {
      //   const aGrade = getNotebookGrade(a)?.total ?? 0;
      //   const bGrade = getNotebookGrade(b)?.total ?? 0;
      //   return sortConfig.direction === 'asc'
      //     ? aGrade - bGrade
      //     : bGrade - aGrade;
      // }

      if (sortConfig.key === 'qual') {
        const aQual = qualResults.get(`${a.dandiset_id}/${a.subfolder}`) ?? false;
        const bQual = qualResults.get(`${b.dandiset_id}/${b.subfolder}`) ?? false;
        return sortConfig.direction === 'asc'
          ? (aQual === bQual ? 0 : aQual ? 1 : -1)
          : (aQual === bQual ? 0 : aQual ? -1 : 1);
      }

      if (sortConfig.key === 'rank') {
        const aRank = rankResults.get(`${a.dandiset_id}/${a.subfolder}`) ?? Number.MAX_SAFE_INTEGER;
        const bRank = rankResults.get(`${b.dandiset_id}/${b.subfolder}`) ?? Number.MAX_SAFE_INTEGER;
        return sortConfig.direction === 'asc'
          ? aRank - bRank
          : bRank - aRank;
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
  }, [notebooks, sortConfig, selectedDandiset, qualResults, rankResults]);

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
              {/* <TableCell>Critiques</TableCell> */}
              {/* <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'grade'}
                  direction={sortConfig.key === 'grade' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('grade')}
                >
                  Grade
                </TableSortLabel>
              </TableCell> */}
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'qual'}
                  direction={sortConfig.key === 'qual' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('qual')}
                >
                  Qual
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortConfig.key === 'rank'}
                  direction={sortConfig.key === 'rank' ? sortConfig.direction : 'asc'}
                  onClick={() => handleSort('rank')}
                >
                  Rank
                </TableSortLabel>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAndSortedNotebooks.map((notebook, index) => {
              // const critiqueUrls = getCritiqueUrls(notebook);
              const isRankOne = rankResults.get(`${notebook.dandiset_id}/${notebook.subfolder}`) === 1;
              return (
                <TableRow
                  key={index}
                  sx={isRankOne ? { backgroundColor: 'rgba(76, 175, 80, 0.1)' } : undefined}
                >
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
                  {/* <TableCell>
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
                  </TableCell> */}
                  {/* <TableCell>
                    {(() => {
                      const grading = getNotebookGrade(notebook);
                      if (!grading) return null;
                      return (
                        <Link
                          href={grading.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={grading.thinking}
                          sx={{ cursor: 'pointer' }}
                        >
                          {grading.total}
                        </Link>
                      );
                    })()}
                  </TableCell> */}
                  <TableCell>
                    {qualResults.get(`${notebook.dandiset_id}/${notebook.subfolder}`) !== undefined ? (
                      <Link
                        href={`https://github.com/dandi-ai-notebooks/dandi-ai-notebook-reviews/blob/main/reviews/${modelForReviews}/dandisets/${notebook.dandiset_id}/${notebook.subfolder}/qualification_test.json`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {qualResults.get(`${notebook.dandiset_id}/${notebook.subfolder}`) ? (
                          <Typography component="span" sx={{ color: 'success.main' }}>✓</Typography>
                        ) : '✗'}
                      </Link>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Link
                      href={`https://github.com/dandi-ai-notebooks/dandi-ai-notebook-reviews/blob/main/reviews/${modelForReviews}/dandisets/${notebook.dandiset_id}/comparisons.md`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {rankResults.get(`${notebook.dandiset_id}/${notebook.subfolder}`)}
                    </Link>
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
    else if (model === 'google/gemini-2.5-pro-preview-03-25') return [1.25, 10]
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
