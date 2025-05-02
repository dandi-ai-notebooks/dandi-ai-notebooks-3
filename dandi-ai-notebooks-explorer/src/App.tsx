import { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  CircularProgress,
  Container,
  Typography
} from '@mui/material';
import { Metadata, ReviewResults, ReviewResultType } from './types';
import NotebooksTable from './NotebooksTable';
import axios from 'axios';

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

function App() {
  const [notebooks, setNotebooks] = useState<Metadata[]>([]);
  // const [critiques, setCritiques] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // const [notebookGradings, setNotebookGradings] = useState<NotebookGradingsData>([]);
  const [qualResults, setQualResults] = useState<Map<string, boolean>>(new Map());
  const [rankResults, setRankResults] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    loadData();
  }, []);

  const modelForReviews = 'claude-3.7-sonnet';

  const loadData = async () => {
    try {
      const [notebooksResponse, reviewResultsResponse] = await Promise.all([
        axios.get<Metadata[]>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/notebooks_metadata.json'),
        // axios.get<CritiqueManifest>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/critiques/manifest.json'),
        // axios.get<NotebookGradingsData>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/notebook_gradings.json'),
        axios.get<ReviewResults>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebook-reviews/refs/heads/main/results.json')
      ]);
      setNotebooks(notebooksResponse.data);
      // setCritiques(new Set(critiquesResponse.data.files));
      // setNotebookGradings(gradingsResponse.data);

      const results = reviewResultsResponse.data.results.filter(r => r.model === modelForReviews);
      const qualResults = new Map(
        results
          .filter((r): r is Extract<ReviewResultType, {type: 'qualification_test'}> => r.type === 'qualification_test')
          .map(r => [`${r.dandiset_id}/${r.subfolder}`, r.passing])
      );
      const rankResults = new Map(
        results
          .filter((r): r is Extract<ReviewResultType, {type: 'rankings'}> => r.type === 'rankings')
          .flatMap(r => r.notebooks.map((n, i) => [`${r.dandiset_id}/${n.subfolder}`, i + 1]))
      );
      setQualResults(qualResults);
      setRankResults(rankResults);
    } catch (err) {
      setError('Failed to load data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth={false}>
        <NotebooksTable
          notebooks={notebooks}
          // critiques={critiques}
          // notebookGradings={notebookGradings}
          qualResults={qualResults}
          rankResults={rankResults}
          modelForReviews={modelForReviews}
        />
      </Container>
    </ThemeProvider>
  );
}

export default App;
