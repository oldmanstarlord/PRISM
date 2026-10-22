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
        bgcolor: "#F9EBD7",
        borderRadius: 0,
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
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
          <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1.05rem", color: "#292D2A" }}>
            Research Notes & Thesis
          </Typography>
          <Chip
            size="small"
            label={`${notes.length} ${notes.length === 1 ? "note" : "notes"}`}
            sx={{
              bgcolor: notes.length > 0 ? "#DCE9DE" : "#E3D7C4",
              color: notes.length > 0 ? "#046A38" : "#292D2A",
              fontWeight: 700,
              fontSize: "0.75rem",
              borderRadius: 0,
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
              bgcolor: "#046A38",
              color: "#F9EBD7",
              fontSize: "0.8rem",
              py: 0.5,
              px: 1.5,
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            + New Note
          </Button>
          <IconButton size="small" sx={{ color: "#686B64", borderRadius: 0 }}>
            {expanded ? "▲" : "▼"}
          </IconButton>
        </Stack>
      </Stack>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ mt: 2.5 }}>
          {/* Search bar and Tag Filters */}
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1.5}
            sx={{ mb: 2, alignItems: { xs: "stretch", sm: "center" } }}
          >
            {externalSearchQuery === undefined && (
              <TextField
                size="small"
                placeholder={`Search notes for ${normSymbol}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                sx={{ flex: 1, "& .MuiInputBase-input": { fontSize: "0.85rem" } }}
              />
            )}

            {availableTags.length > 0 && (
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 600, mr: 0.5 }}>
                  Tag:
                </Typography>
                <Chip
                  size="small"
                  label="All"
                  clickable
                  onClick={() => setSelectedTag(null)}
                  sx={{
                    fontSize: "0.72rem",
                    borderRadius: 0,
                    fontWeight: 600,
                    bgcolor: selectedTag === null ? "#046A38" : "#E3D7C4",
                    color: selectedTag === null ? "#F9EBD7" : "#292D2A",
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
                      fontSize: "0.72rem",
                      borderRadius: 0,
                      fontWeight: 600,
                      bgcolor: selectedTag === tag ? "#046A38" : "#E3D7C4",
                      color: selectedTag === tag ? "#F9EBD7" : "#292D2A",
                    }}
                  />
                ))}
              </Stack>
            )}
          </Stack>

          {/* Notes List */}
          {loading ? (
            <Typography variant="body2" sx={{ color: "#686B64", py: 2 }}>
              Loading research notes...
            </Typography>
          ) : filteredNotes.length === 0 ? (
            <Box
              sx={{
                p: 3,
                textAlign: "center",
                bgcolor: "#F9EBD7",
                borderRadius: 0,
                boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
              }}
            >
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1 }}>
                {notes.length === 0
                  ? `No research notes recorded for ${normSymbol} yet.`
                  : "No notes match the current search or tag filter."}
              </Typography>
              {notes.length === 0 && (
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleOpenCreate}
                  sx={{ fontSize: "0.8rem", mt: 0.5, bgcolor: "#046A38", color: "#F9EBD7", borderRadius: 0, boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}
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
                    p: 2,
                    bgcolor: "#F9EBD7",
                    borderRadius: 0,
                    boxShadow: "0 3px 8px rgba(41,45,42,0.08)",
                    transition: "box-shadow 0.15s",
                    "&:hover": {
                      boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
                    },
                  }}
                >
                  <Stack
                    direction="row"
                    sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}
                  >
                    {/* Tags */}
                    <Stack direction="row" spacing={0.6} sx={{ flexWrap: "wrap", gap: 0.5 }}>
                      {note.tags.length > 0 ? (
                        note.tags.map((tag) => (
                          <Chip
                            key={tag}
                            size="small"
                            label={tag}
                            sx={{
                              fontSize: "0.72rem",
                              height: 22,
                              borderRadius: 0,
                              bgcolor: "#DCE9DE",
                              color: "#046A38",
                              fontWeight: 600,
                            }}
                          />
                        ))
                      ) : (
                        <Typography variant="caption" sx={{ color: "#686B64" }}>
                          No tags
                        </Typography>
                      )}
                    </Stack>

                    {/* Actions: Edit & Delete */}
                    <Stack direction="row" spacing={0.5}>
                      <Tooltip title="Edit note">
                        <IconButton size="small" onClick={() => handleOpenEdit(note)} sx={{ borderRadius: 0, fontSize: "0.75rem", fontWeight: 600 }}>
                          Edit
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete note">
                        <IconButton
                          size="small"
                          onClick={() => setDeleteConfirmId(note.id)}
                          sx={{ color: "#B8321A", borderRadius: 0, fontSize: "0.75rem", fontWeight: 600 }}
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
                      color: "#292D2A",
                      lineHeight: 1.6,
                      fontSize: "0.9rem",
                      mb: 1.5,
                    }}
                  >
                    {note.content}
                  </Typography>

                  {/* Timestamps */}
                  <Stack
                    direction="row"
                    spacing={2}
                    sx={{
                      fontSize: "0.75rem",
                      color: "#686B64",
                      pt: 0.5,
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
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
              color: "#292D2A",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
          {editingNote ? `Edit Note: ${normSymbol}` : `New Research Note: ${normSymbol}`}
          {companyName && (
            <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
              {companyName}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 0 }} onClose={() => setErrorMsg(null)}>
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
              mb: 2.5,
              "& .MuiInputBase-input": {
                fontSize: "0.92rem",
                lineHeight: 1.6,
              },
            }}
          />

          {/* Tags Selection */}
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: "#292D2A" }}>
            Select or Suggest Tags
          </Typography>
          <Stack direction="row" spacing={0.6} sx={{ flexWrap: "wrap", gap: 0.6, mb: 2 }}>
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
                    fontSize: "0.78rem",
                    borderRadius: 0,
                    fontWeight: 600,
                    bgcolor: selected ? "#046A38" : "#E3D7C4",
                    color: selected ? "#F9EBD7" : "#292D2A",
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
              sx={{ flex: 1, "& .MuiInputBase-input": { fontSize: "0.85rem" } }}
            />
            <Button
              size="small"
              variant="contained"
              onClick={handleAddCustomTag}
              disabled={!customTagInput.trim()}
              sx={{ textTransform: "none", fontSize: "0.8rem", bgcolor: "#046A38", color: "#F9EBD7", borderRadius: 0, boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}
            >
              Add Tag
            </Button>
          </Stack>

          {/* Active Tags Preview */}
          {activeTags.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 600 }}>
                Selected tags:
              </Typography>
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mt: 0.5 }}>
                {activeTags.map((tag) => (
                  <Chip
                    key={tag}
                    label={tag}
                    size="small"
                    onDelete={() => handleToggleTag(tag)}
                    sx={{
                      fontSize: "0.75rem",
                      height: 24,
                      borderRadius: 0,
                      bgcolor: "#DCE9DE",
                      color: "#046A38",
                      fontWeight: 600,
                    }}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#03532c" },
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
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
              color: "#292D2A",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: "#292D2A" }}>Delete Research Note?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "#686B64" }}>
            Are you sure you want to delete this research note? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, pb: 2 }}>
          <Button onClick={() => setDeleteConfirmId(null)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            sx={{
              bgcolor: "#E34222",
              color: "#F9EBD7",
              fontWeight: 700,
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#b8321a" },
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
