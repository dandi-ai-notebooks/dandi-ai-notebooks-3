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
import { Metadata, CritiqueManifest } from './types';
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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [notebooksResponse, critiquesResponse] = await Promise.all([
        axios.get<Metadata[]>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/notebooks_metadata.json'),
        axios.get<CritiqueManifest>('https://raw.githubusercontent.com/dandi-ai-notebooks/dandi-ai-notebooks-3/refs/heads/main/critiques/manifest.json')
      ]);
      setNotebooks(notebooksResponse.data);
      setCritiques(new Set(critiquesResponse.data.files));
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
        <NotebooksTable notebooks={notebooks} critiques={critiques} />
      </Container>
    </ThemeProvider>
  );
}

export default App;
