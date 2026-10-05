import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, CardContent, Container, Stack, TextField, Typography } from "@mui/material";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiBase, useApi } from "./api";
import type { Watchlist } from "./types";

const schema = z.object({
  name: z.string().trim().min(1).max(120),
  symbols: z.string().trim(),
});
type FormValues = z.infer<typeof schema>;

export default function WatchlistsPage() {
  const queryClient = useQueryClient();
  const { data = [] } = useApi<Watchlist[]>("/watchlists");
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<FormValues>({
    defaultValues: { name: "", symbols: "" },
  });
  const create = useMutation({
    mutationFn: async (values: FormValues) => {
      const symbols = values.symbols.split(",").map((item) => item.trim()).filter(Boolean);
      const response = await fetch(`${apiBase}/watchlists`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: values.name, items: symbols.map((symbol) => ({ symbol, thresholds: {} })) }),
      });
      if (!response.ok) throw new Error(await response.text());
    },
    onSuccess: async () => { reset(); await queryClient.invalidateQueries({ queryKey: ["/watchlists"] }); },
  });
  const remove = async (id: string) => {
    await fetch(`${apiBase}/watchlists/${id}`, { method: "DELETE" });
    await queryClient.invalidateQueries({ queryKey: ["/watchlists"] });
  };
  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 800, mb: 2 }}>Watchlists</Typography>
      <Stack component="form" onSubmit={handleSubmit((value) => {
        const parsed = schema.safeParse(value);
        if (!parsed.success) {
          setError("name", { message: parsed.error.issues[0]?.message ?? "Invalid watchlist" });
          return;
        }
        create.mutate(parsed.data);
      })} spacing={2} sx={{ mb: 4 }}>
        <TextField label="Watchlist name" {...register("name")} error={Boolean(errors.name)} helperText={errors.name?.message} />
        <TextField label="Symbols (comma separated)" {...register("symbols")} />
        <Button type="submit" variant="contained" disabled={create.isPending}>Create watchlist</Button>
        {create.error && <Alert severity="error">{create.error.message}</Alert>}
      </Stack>
      <Stack spacing={2}>{data.map((item) => (
        <Card variant="outlined" key={item.id}><CardContent>
          <Stack direction="row" sx={{ justifyContent: "space-between" }}>
            <Typography variant="h6">{item.name}</Typography>
            <Button color="error" onClick={() => void remove(item.id)}>Delete</Button>
          </Stack>
          <Typography color="text.secondary">{item.items.map((entry) => entry.symbol).join(", ") || "No items"}</Typography>
        </CardContent></Card>
      ))}</Stack>
    </Container>
  );
}
