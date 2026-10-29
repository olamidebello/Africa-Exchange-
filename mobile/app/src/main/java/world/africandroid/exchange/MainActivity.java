package world.africandroid.exchange;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.net.Uri;
import android.graphics.Bitmap;
import android.view.View;
import android.widget.*;
import android.webkit.*;

public class MainActivity extends Activity {
    private WebView web;
    private TextView message;
    private boolean openExternal(Uri uri) {
        String scheme = uri.getScheme();
        if (!"https".equals(scheme) && !"mailto".equals(scheme) && !"tel".equals(scheme)) return true;
        try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
        catch (ActivityNotFoundException e) { Toast.makeText(this, "No application can open this link", Toast.LENGTH_LONG).show(); }
        return true;
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        LinearLayout controls = new LinearLayout(this);
        Button home = new Button(this); home.setText("Home"); controls.addView(home);
        Button reload = new Button(this); reload.setText("Reload"); controls.addView(reload);
        Button browser = new Button(this); browser.setText("Browser"); controls.addView(browser);
        layout.addView(controls);
        message = new TextView(this); message.setPadding(16, 12, 16, 12); layout.addView(message);
        web = new WebView(this); layout.addView(web, new LinearLayout.LayoutParams(-1, 0, 1)); setContentView(layout);
        web.getSettings().setJavaScriptEnabled(true); web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false); web.getSettings().setAllowContentAccess(false);
        web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView v, String url, Bitmap icon) { message.setText("Loading Africa Exchange…"); message.setVisibility(View.VISIBLE); }
            @Override public void onPageFinished(WebView v, String url) { if ("Loading Africa Exchange…".contentEquals(message.getText())) message.setVisibility(View.GONE); }
            @Override public void onReceivedError(WebView v, WebResourceRequest request, WebResourceError error) { if (request.isForMainFrame()) { message.setText("Cannot connect. Check your internet connection and tap Reload."); message.setVisibility(View.VISIBLE); } }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equals(uri.getScheme()) && "exchange.africandroid.world".equals(uri.getHost()) && !uri.getPath().endsWith(".apk")) return false;
                return openExternal(uri);
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mime, size) -> openExternal(Uri.parse(url)));
        home.setOnClickListener(v -> web.loadUrl("https://exchange.africandroid.world/"));
        reload.setOnClickListener(v -> web.reload());
        browser.setOnClickListener(v -> openExternal(Uri.parse("https://exchange.africandroid.world/")));
        if (state == null) web.loadUrl("https://exchange.africandroid.world/"); else web.restoreState(state);
    }
    @Override protected void onSaveInstanceState(Bundle state) { web.saveState(state); super.onSaveInstanceState(state); }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onDestroy() { web.destroy(); super.onDestroy(); }
}
