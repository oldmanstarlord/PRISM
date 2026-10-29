import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  deleteNote,
  getNotesBySymbol,
  type ResearchNote,
  saveNote,
} from "./journalStorage";

export interface StockResearchNotesProps {
  symbol: string;
  companyName?: string;
  defaultExpanded?: boolean;
  onNotesCountChange?: (count: number) => void;
  externalSearchQuery?: string;
}

const PRESET_TAG_SUGGESTIONS = [
  "Review",
  "Investment Thesis",
  "Valuation",
  "Earnings Catalyst",
  "High Volatility",
  "Margin Moat",
  "Management",
];

export default function StockResearchNotes({
  symbol,
  companyName,
  defaultExpanded = true,
  onNotesCountChange,
  externalSearchQuery,
}: StockResearchNotesProps) {
  const normSymbol = symbol.trim().toUpperCase();
  const [notes, setNotes] = useState<ResearchNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Filter & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  // Dialog State (Create / Edit)
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<ResearchNote | null>(null);
  const [contentInput, setContentInput] = useState("");
  const [customTagInput, setCustomTagInput] = useState("");
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Delete Confirmation
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const loadNotes = async () => {
    setLoading(true);
    try {
      const data = await getNotesBySymbol(normSymbol);
      setNotes(data);
      if (onNotesCountChange) {
        onNotesCountChange(data.length);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadNotes();
  }, [normSymbol]); // eslint-disable-line react-hooks/exhaustive-deps

  // Extract all unique tags present across this stock's notes
  const availableTags = useMemo(() => {
    const set = new Set<string>();
    for (const note of notes) {
      for (const tag of note.tags) {
        set.add(tag);
      }
    }
    return Array.from(set).sort();
  }, [notes]);

  // Filter notes by search query and selected tag
  const effectiveQuery = (externalSearchQuery !== undefined ? externalSearchQuery : searchQuery).trim().toLowerCase();
  const filteredNotes = useMemo(() => {
    return notes.filter((n) => {
      const matchesSearch =
        !effectiveQuery ||
        n.content.toLowerCase().includes(effectiveQuery) ||
        n.tags.some((t) => t.toLowerCase().includes(effectiveQuery));

      const matchesTag = !selectedTag || n.tags.includes(selectedTag);
      return matchesSearch && matchesTag;
    });
  }, [notes, effectiveQuery, selectedTag]);

  const handleOpenCreate = () => {
    setEditingNote(null);
    setContentInput("");
    setActiveTags([]);
    setCustomTagInput("");
    setErrorMsg(null);
    setDialogOpen(true);
  };

  const handleOpenEdit = (note: ResearchNote) => {
    setEditingNote(note);
    setContentInput(note.content);
    setActiveTags([...note.tags]);
    setCustomTagInput("");
    setErrorMsg(null);
    setDialogOpen(true);
  };

  const handleToggleTag = (tag: string) => {
    setActiveTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleAddCustomTag = () => {
    const trimmed = customTagInput.trim();
    if (trimmed && !activeTags.includes(trimmed)) {
      setActiveTags((prev) => [...prev, trimmed]);
      setCustomTagInput("");
    }
  };

  const handleSave = async () => {
    if (!contentInput.trim()) {
      setErrorMsg("Please enter note content.");
      return;
    }

    try {
      await saveNote({
        id: editingNote?.id,
        symbol: normSymbol,
        content: contentInput.trim(),
        tags: activeTags,
      });
      setDialogOpen(false);
      await loadNotes();
    } catch {
      setErrorMsg("Failed to save research note. Please try again.");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteNote(id);
      setDeleteConfirmId(null);
      await loadNotes();
    } catch {
      // Graceful fallback
    }
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <Paper
      id="research-notes-section"
      elevation={0}
      sx={{
        p: { xs: 2, sm: 2.5 },
        bgcolor: "var(--bg)",
        borderRadius: "var(--radius)",
        boxShadow: "none",
      }}
    >
      {/* Header with expand toggle and action button */}
      <Stack
        direction="row"
        sx={{
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: "var(--text-title)", color: "var(--white)" }}>
            Research Notes & Thesis
          </Typography>
          <Chip
            size="small"
            label={`${notes.length} ${notes.length === 1 ? "note" : "notes"}`}
            sx={{
              bgcolor: notes.length > 0 ? "var(--line)" : "var(--line)",
              color: notes.length > 0 ? "var(--up)" : "var(--white)",
              fontWeight: 600,
              fontSize: "var(--text-title)",
              borderRadius: "var(--radius)",
            }}
          />
        </Stack>

        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Button
            size="small"
            variant="contained"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(true);
              handleOpenCreate();
            }}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              fontSize: "var(--text-title)",
              py: "var(--space-1)",
              px: "var(--space-2)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--up)" },
            }}
          >
            + New Note
          </Button>
          <IconButton aria-label={expanded ? "Hide research notes" : "Show research notes"} aria-expanded={expanded} size="small" sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            {expanded ? "▲" : "▼"}
          </IconButton>
        </Stack>
      </Stack>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ mt: "var(--space-3)" }}>
          {/* Search bar and Tag Filters */}
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1.5}
            sx={{ mb: "var(--space-2)", alignItems: { xs: "stretch", sm: "center" } }}
          >
            {externalSearchQuery === undefined && (
              <TextField
                size="small"
                placeholder={`Search notes for ${normSymbol}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                sx={{ flex: 1, "& .MuiInputBase-input": { fontSize: "var(--text-title)" } }}
              />
            )}

            {availableTags.length > 0 && (
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, mr: "var(--space-1)" }}>
                  Tag:
                </Typography>
                <Chip
                  size="small"
                  label="All"
                  clickable
                  onClick={() => setSelectedTag(null)}
                  sx={{
                    fontSize: "var(--text-title)",
                    borderRadius: "var(--radius)",
                    fontWeight: 600,
                    bgcolor: selectedTag === null ? "var(--up)" : "var(--line)",
                    color: selectedTag === null ? "var(--bg)" : "var(--white)",
                  }}
                />
                {availableTags.map((tag) => (
                  <Chip
                    key={tag}
                    size="small"
                    label={tag}
                    clickable
                    onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                    sx={{
                      fontSize: "var(--text-title)",
                      borderRadius: "var(--radius)",
                      fontWeight: 600,
                      bgcolor: selectedTag === tag ? "var(--up)" : "var(--line)",
                      color: selectedTag === tag ? "var(--bg)" : "var(--white)",
                    }}
                  />
                ))}
              </Stack>
            )}
          </Stack>

          {/* Notes List */}
          {loading ? (
            <Typography variant="body2" sx={{ color: "var(--gray)", py: "var(--space-2)" }}>
              Loading research notes...
            </Typography>
          ) : filteredNotes.length === 0 ? (
            <Box
              sx={{
                p: "var(--space-3)",
                textAlign: "center",
                bgcolor: "var(--bg)",
                borderRadius: "var(--radius)",
                boxShadow: "none",
              }}
            >
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-1)" }}>
                {notes.length === 0
                  ? `No research notes recorded for ${normSymbol} yet.`
                  : "No notes match the current search or tag filter."}
              </Typography>
              {notes.length === 0 && (
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleOpenCreate}
                  sx={{ fontSize: "var(--text-title)", mt: "var(--space-1)", bgcolor: "var(--up)", color: "var(--line)", borderRadius: "var(--radius)", boxShadow: "none" }}
                >
                  Write First Thesis Note
                </Button>
              )}
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {filteredNotes.map((note) => (
                <Paper
                  key={note.id}
                  elevation={0}
                  sx={{
                    p: "var(--space-2)",
                    bgcolor: "var(--bg)",
                    borderRadius: "var(--radius)",
                    boxShadow: "none",
                    transition: "none",
                    "&:hover": {
                      boxShadow: "none",
                    },
                  }}
                >
                  <Stack
                    direction="row"
                    sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: "var(--space-1)" }}
                  >
                    {/* Tags */}
                    <Stack direction="row" spacing={0.6} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                      {note.tags.length > 0 ? (
                        note.tags.map((tag) => (
                          <Chip
                            key={tag}
                            size="small"
                            label={tag}
                            sx={{
                              fontSize: "var(--text-title)",
                              height: 22,
                              borderRadius: "var(--radius)",
                              bgcolor: "var(--line)",
                              color: "var(--up)",
                              fontWeight: 600,
                            }}
                          />
                        ))
                      ) : (
                        <Typography variant="caption" sx={{ color: "var(--gray)" }}>
                          No tags
                        </Typography>
                      )}
                    </Stack>

                    {/* Actions: Edit & Delete */}
                    <Stack direction="row" spacing={0.5}>
                      <Tooltip title="Edit note">
                        <IconButton size="small" onClick={() => handleOpenEdit(note)} sx={{ borderRadius: "var(--radius)", fontSize: "var(--text-title)", fontWeight: 600 }}>
                          Edit
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete note">
                        <IconButton
                          size="small"
                          onClick={() => setDeleteConfirmId(note.id)}
                          sx={{ color: "var(--down)", borderRadius: "var(--radius)", fontSize: "var(--text-title)", fontWeight: 600 }}
                        >
                          Delete
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Stack>

                  {/* Note Content (plain text with preserved whitespace) */}
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: "pre-wrap",
                      color: "var(--white)",
                      lineHeight: "var(--leading)",
                      fontSize: "var(--text-title)",
                      mb: "var(--space-2)",
                    }}
                  >
                    {note.content}
                  </Typography>

                  {/* Timestamps */}
                  <Stack
                    direction="row"
                    spacing={2}
                    sx={{
                      fontSize: "var(--text-title)",
                      color: "var(--gray)",
                      pt: "var(--space-1)",
                    }}
                  >
                    <span>Created: {formatTimestamp(note.createdAt)}</span>
                    {note.updatedAt !== note.createdAt && (
                      <span>Updated: {formatTimestamp(note.updatedAt)}</span>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}
        </Box>
      </Collapse>

      {/* Note Create / Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, pb: "var(--space-1)", color: "var(--white)" }}>
          {editingNote ? `Edit Note: ${normSymbol}` : `New Research Note: ${normSymbol}`}
          {companyName && (
            <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
              {companyName}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent sx={{ pt: "var(--space-1)" }}>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: "var(--space-2)", borderRadius: "var(--radius)" }} onClose={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          {/* Note Plain Text Area */}
          <TextField
            autoFocus
            multiline
            rows={5}
            fullWidth
            placeholder="Record your thesis, research findings, risk factors, or qualitative context..."
            value={contentInput}
            onChange={(e) => setContentInput(e.target.value)}
            sx={{
              mb: "var(--space-3)",
              "& .MuiInputBase-input": {
                fontSize: "var(--text-title)",
                lineHeight: "var(--leading)",
              },
            }}
          />

          {/* Tags Selection */}
          <Typography variant="subtitle2" sx={{ mb: "var(--space-1)", fontWeight: 600, color: "var(--white)" }}>
            Select or Suggest Tags
          </Typography>
          <Stack direction="row" spacing={0.6} sx={{ flexWrap: "wrap", gap: "var(--space-1)", mb: "var(--space-2)" }}>
            {PRESET_TAG_SUGGESTIONS.map((tag) => {
              const selected = activeTags.includes(tag);
              return (
                <Chip
                  key={tag}
                  label={tag}
                  size="small"
                  clickable
                  onClick={() => handleToggleTag(tag)}
                  sx={{
                    fontSize: "var(--text-title)",
                    borderRadius: "var(--radius)",
                    fontWeight: 600,
                    bgcolor: selected ? "var(--up)" : "var(--line)",
                    color: selected ? "var(--bg)" : "var(--white)",
                  }}
                />
              );
            })}
          </Stack>

          {/* Custom Tag Input */}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <TextField
              size="small"
              placeholder="Add custom tag..."
              value={customTagInput}
              onChange={(e) => setCustomTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddCustomTag();
                }
              }}
              sx={{ flex: 1, "& .MuiInputBase-input": { fontSize: "var(--text-title)" } }}
            />
            <Button
              size="small"
              variant="contained"
              onClick={handleAddCustomTag}
              disabled={!customTagInput.trim()}
              sx={{ textTransform: "none", fontSize: "var(--text-title)", bgcolor: "var(--up)", color: "var(--line)", borderRadius: "var(--radius)", boxShadow: "none" }}
            >
              Add Tag
            </Button>
          </Stack>

          {/* Active Tags Preview */}
          {activeTags.length > 0 && (
            <Box sx={{ mt: "var(--space-2)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
                Selected tags:
              </Typography>
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: "var(--space-1)", mt: "var(--space-1)" }}>
                {activeTags.map((tag) => (
                  <Chip
                    key={tag}
                    label={tag}
                    size="small"
                    onDelete={() => handleToggleTag(tag)}
                    sx={{
                      fontSize: "var(--text-title)",
                      height: 24,
                      borderRadius: "var(--radius)",
                      bgcolor: "var(--line)",
                      color: "var(--up)",
                      fontWeight: 600,
                    }}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: "var(--space-3)", py: "var(--space-2)" }}>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--up)" },
            }}
          >
            {editingNote ? "Save Changes" : "Create Note"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        maxWidth="xs"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, color: "var(--white)" }}>Delete Research Note?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "var(--gray)" }}>
            Are you sure you want to delete this research note? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: "var(--space-3)", pb: "var(--space-2)" }}>
          <Button onClick={() => setDeleteConfirmId(null)} sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            sx={{
              bgcolor: "var(--down)",
              color: "var(--white)",
              fontWeight: 600,
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--down)" },
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
