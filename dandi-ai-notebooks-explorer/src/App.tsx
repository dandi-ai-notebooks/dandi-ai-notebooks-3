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
import { Metadata, CritiqueManifest, NotebookRankingsData } from './types';
import NotebooksTable from './NotebooksTable';
import axios from 'axios';

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

function App() {
  const [notebooks, setNotebooks] = useState<Metadata[]>([]);
  const [critiques, setCritiques] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notebookRankings, setNotebookRankings] = useState<NotebookRankingsData>({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [notebooksResponse, critiquesResponse, rankingsResponse] = await Promise.all([
        axios.get<Metadata[]>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/notebooks_metadata.json'),
        axios.get<CritiqueManifest>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/critiques/manifest.json'),
        axios.get<NotebookRankingsData>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/notebook_rankings.json')
      ]);
      setNotebooks(notebooksResponse.data);
      setCritiques(new Set(critiquesResponse.data.files));
      setNotebookRankings(rankingsResponse.data);
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
        <NotebooksTable notebooks={notebooks} critiques={critiques} notebookRankings={notebookRankings} />
      </Container>
    </ThemeProvider>
  );
}

export default App;
