# LandFall AI - Mobile App Deployment Guide

## Overview
To make LandFall AI available on the Google Play Store as a mobile app, we'll use **Capacitor** by Ionic. This wraps your React web app into a native Android (and iOS) application.

## Prerequisites
- Node.js and npm installed
- Android Studio for Android builds
- Google Play Developer account ($25 one-time fee)

## Step 1: Install Capacitor

```bash
cd /app/frontend
npm install @capacitor/core @capacitor/cli
npx cap init "LandFall AI" "com.landfall.ai" --web-dir build
npm install @capacitor/android
```

## Step 2: Configure Capacitor

Create `/app/frontend/capacitor.config.json`:
```json
{
  "appId": "com.landfall.ai",
  "appName": "LandFall AI",
  "webDir": "build",
  "android": {
    "backgroundColor": "#0a0a0b"
  }
}
```

## Step 3: Add Android Platform

```bash
npx cap add android
```

This creates an `android/` folder with a native Android project.

## Step 4: Build Your React App

```bash
REACT_APP_BACKEND_URL=https://your-api-domain.example.com npm run build
npx cap sync android
```

This copies your built React app into the Android wrapper.

## Step 5: Configure Android App

Edit `/app/frontend/android/app/src/main/AndroidManifest.xml`:
- Add internet permission
- Configure app icons
- Set proper orientation

## Step 6: Build APK/AAB

### Option A: Using Android Studio (Recommended)
1. Open `/app/frontend/android` in Android Studio
2. Let Gradle sync
3. Build → Generate Signed Bundle/APK
4. Create a keystore for signing
5. Build release AAB (Android App Bundle)

### Option B: Command Line
```bash
cd android
./gradlew assembleRelease
# Output: android/app/build/outputs/apk/release/app-release.apk
```

## Step 7: Prepare for Play Store

1. **Create Store Listing:**
   - App title: "LandFall AI - MTG Commander Deck Builder"
   - Short description: "Optimize your Commander decks with AI-powered analysis"
   - Full description: Detailed feature list
   - Screenshots: 8 required (phone + tablet)
   - Feature graphic: 1024x500px
   - Icon: 512x512px

2. **Content Rating:**
   - Complete Google's content rating questionnaire
   - LandFall AI should be rated for Everyone

3. **Privacy Policy:**
   - Required by Google Play
   - Host at: https://yourwebsite.com/privacy-policy
   - Must explain data collection/usage

4. **App Release:**
   - Upload AAB file
   - Set pricing (Free)
   - Select countries
   - Submit for review (takes 1-3 days)

## Step 8: Required Assets

### App Icon (512x512px)
Create a high-res version of the forest mana symbol for the app icon.

### Feature Graphic (1024x500px)
Banner showing LandFall AI logo and key features.

### Screenshots (minimum 2, recommended 8)
- Dashboard view
- Deck import screen
- Analysis results with card images
- Commander lookup
- Random commander
- Deck viewer

## Step 9: Updates & Maintenance

When you update the web app:
```bash
cd /app/frontend
REACT_APP_BACKEND_URL=https://your-api-domain.example.com npm run build
npx cap sync android
# Then rebuild in Android Studio and upload new version to Play Store
```

## Alternative: Progressive Web App (PWA)

For faster deployment, convert to PWA:

1. **Add Service Worker:**
```bash
npm install workbox-webpack-plugin
```

2. **Configure manifest.json:**
```json
{
  "name": "LandFall AI",
  "short_name": "LandFall",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#00733e",
  "background_color": "#0a0a0b",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

3. Users can "Add to Home Screen" on mobile browsers
4. Works on both Android and iOS
5. No Play Store approval needed
6. Automatic updates when you deploy web changes

## Recommended Approach

**Start with PWA** for immediate mobile support, then **add Capacitor** for Play Store presence:

1. Week 1: Implement PWA (works immediately)
2. Week 2: Set up Capacitor for native app
3. Week 3: Prepare Play Store assets
4. Week 4: Submit to Play Store

## Mobile-Specific Optimizations Already Done

✅ Responsive design with Tailwind
✅ Touch-friendly buttons (min 44px)
✅ Mobile viewport configured
✅ Fast loading with code splitting
✅ Works on small screens

## Cost Breakdown

- Google Play Developer Account: $25 (one-time)
- App icons/assets: Free (create yourself) or $50-200 (hire designer)
- Total: $25-225

## Timeline

- PWA setup: 1-2 hours
- Capacitor setup: 2-4 hours
- Play Store submission: 1-3 days review
- Total: Can be live as PWA immediately, Play Store in ~1 week

## Support

- Capacitor Docs: https://capacitorjs.com/docs
- Play Store Console: https://play.google.com/console
- PWA Guide: https://web.dev/progressive-web-apps/
