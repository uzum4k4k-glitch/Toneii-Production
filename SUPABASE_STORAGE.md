# Persistent audio uploads with Supabase Storage

Toneii can store uploaded BGM and SFX files in Supabase Storage instead of the Git repository or the app's local filesystem. The existing host and guest pages continue to work: they request `/static/audio/<file>`, and the server redirects Supabase-backed audio to its public Storage URL. The upload API response also includes each file's direct `url`.

## Configure Supabase

1. Create a Supabase project.
2. In **Storage**, create a bucket named `toneii-audio` (or choose another name in the environment variable below) and set it to **Public**. Public access lets guests' audio players fetch the music without exposing any server secret.
3. In the project's API settings, copy the project URL and the **service_role** key. Keep the service-role key private; never put it in HTML, JavaScript, or a public repository.
4. Set these environment variables in the server's hosting dashboard (or your local shell):

   - `SUPABASE_URL` — for example, `https://your-project-id.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` — the server-only service role key
   - `SUPABASE_STORAGE_BUCKET` — `toneii-audio` (optional; this is the default)

   For local development, set them in your terminal before starting Uvicorn. Do not commit credentials to GitHub. Restart/redeploy the app after setting them.

## Upload and playback

Upload BGM/SFX from the existing host page as usual. The server validates the audio extension and 50 MB per-file limit, uploads the object to Supabase, and stores its object key and metadata in `toneii.db`. The web players follow a redirect to the bucket's public URL. Deleting a library entry also deletes the corresponding object from Supabase.

The SQLite migration adds `storage_type` automatically. Existing local audio records keep working; newly uploaded files use Supabase. Existing files in the repository are not moved automatically—upload them again through the host page if they should live in Supabase.

## Important deployment note

Supabase makes the audio files persistent, but the app's SQLite database also needs persistent storage for the library metadata. If your hosting platform has ephemeral disks, configure a persistent volume for `toneii.db` or move the metadata to a managed database; otherwise the audio remains in Supabase but the app may lose its list of files after a redeploy. Set reasonable Supabase Storage limits and review its pricing/quotas for your usage.
