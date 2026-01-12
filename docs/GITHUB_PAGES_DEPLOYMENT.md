# GitHub Pages Deployment Guide

This guide explains how to deploy the exported HTML dashboard to GitHub Pages for public access.

## Overview

GitHub Pages allows you to host static HTML files directly from your GitHub repository. After exporting the aggregate statistics dashboard from the webapp, you can push it to GitHub and it will be automatically served at a public URL.

## Prerequisites

- Git installed and configured
- GitHub account with access to the repository
- Repository push permissions
- HTML file exported from the webapp (saved to `docs/aggregate-stats.html`)

## Step-by-Step Deployment

### Step 1: Export HTML from Webapp

1. Navigate to the Aggregate Statistics page in the webapp
2. Click the "Export HTML" button
3. You should see a success message: "HTML exported successfully to docs/aggregate-stats.html"
4. The file is now saved in the `docs/` directory of your repository

### Step 2: Verify the File Exists

Check that the file was created:

```bash
ls -la docs/aggregate-stats.html
```

You should see the file listed. If it doesn't exist, try exporting again from the webapp.

### Step 3: Configure GitHub Pages

1. Go to your GitHub repository on GitHub.com
2. Click on **Settings** (in the repository navigation bar)
3. Scroll down to **Pages** in the left sidebar
4. Under **Source**, select:
   - **Branch**: `main` (or your default branch)
   - **Folder**: `/docs`
5. Click **Save**

GitHub Pages will now serve files from the `docs/` directory.

### Step 4: Commit and Push to GitHub

```bash
# Navigate to repository root
cd /path/to/bball

# Check git status
git status

# Add the exported HTML file
git add docs/aggregate-stats.html

# Commit the file
git commit -m "Export aggregate statistics dashboard for GitHub Pages"

# Push to GitHub
git push origin main
```

**Note**: If you're working on a different branch, replace `main` with your branch name.

### Step 5: Access Your Published Site

After pushing, GitHub Pages will automatically build and deploy your site. This usually takes 1-2 minutes.

Your dashboard will be available at:
```
https://[username].github.io/[repository-name]/aggregate-stats.html
```

Replace:
- `[username]` with your GitHub username or organization name
- `[repository-name]` with your repository name

**Example**: If your username is `adamvoliva` and repository is `bball`, the URL would be:
```
https://adamvoliva.github.io/bball/aggregate-stats.html
```

### Step 6: Verify Deployment

1. Wait 1-2 minutes for GitHub Pages to build
2. Visit the URL from Step 5
3. Verify that:
   - The page loads correctly
   - All charts are displayed
   - All data is visible
   - The styling matches the webapp version

## Updating the Dashboard

To update the dashboard with new data:

1. Export a new HTML file from the webapp (this will overwrite the existing file)
2. Commit and push the updated file:
   ```bash
   git add docs/aggregate-stats.html
   git commit -m "Update aggregate statistics dashboard"
   git push origin main
   ```
3. GitHub Pages will automatically rebuild with the new content (usually within 1-2 minutes)

## Troubleshooting

### Issue: File Not Found (404 Error)

**Symptoms**: Visiting the GitHub Pages URL returns a 404 error

**Solutions**:
- Verify GitHub Pages is configured to serve from `/docs` folder (Step 3)
- Check that the file is actually in the `docs/` directory: `ls docs/aggregate-stats.html`
- Ensure the file was committed and pushed: `git log docs/aggregate-stats.html`
- Wait a few minutes - GitHub Pages can take 1-2 minutes to build

### Issue: Page Loads But Charts Don't Display

**Symptoms**: HTML page loads but charts are blank or missing

**Solutions**:
- Check browser console for JavaScript errors (F12 → Console)
- Verify Chart.js CDN is accessible (check network tab)
- Ensure all data is embedded in the HTML (the export includes all data inline)
- Try a different browser or clear browser cache

### Issue: Styling Looks Wrong

**Symptoms**: Page loads but styling is broken or missing

**Solutions**:
- Verify CSS is embedded in the HTML (the export includes CSS inline)
- Check browser console for CSS loading errors
- Clear browser cache and reload

### Issue: Export Fails in Webapp

**Symptoms**: Clicking "Export HTML" shows an error message

**Solutions**:
- Check that the backend is running
- Verify `docs/` directory exists and is writable: `ls -la docs/`
- Check backend logs for error messages
- Try the fallback download (the export function will automatically download to browser if backend save fails)

### Issue: GitHub Pages Build Fails

**Symptoms**: GitHub Pages shows a build error in repository settings

**Solutions**:
- Check that the HTML file is valid (open it locally in a browser)
- Verify the file is not too large (GitHub Pages has a 1GB limit per repository)
- Check GitHub Pages build logs in repository Settings → Pages → Build logs
- Ensure file encoding is UTF-8

## Advanced Configuration

### Custom Domain

If you want to use a custom domain:

1. Add a `CNAME` file to the `docs/` directory with your domain name
2. Configure DNS records for your domain to point to GitHub Pages
3. See [GitHub Pages custom domain documentation](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)

### Jekyll Processing

By default, GitHub Pages uses Jekyll to process files. If you encounter issues with Jekyll processing (e.g., underscores in filenames), you can disable it by adding a `.nojekyll` file to the `docs/` directory:

```bash
touch docs/.nojekyll
git add docs/.nojekyll
git commit -m "Disable Jekyll processing for GitHub Pages"
git push origin main
```

## Security Considerations

- The exported HTML file contains all data embedded inline (no external API calls)
- The dashboard is publicly accessible once deployed to GitHub Pages
- No authentication is required to view the dashboard
- Consider data sensitivity before deploying

## Additional Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Pages Custom Domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [GitHub Pages Jekyll](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll)

