package world.africandroid.exchange;
import android.app.Activity;import android.os.Bundle;import android.content.Intent;import android.net.Uri;import android.webkit.*;
public class MainActivity extends Activity {
 WebView web;
 public void onCreate(Bundle state){super.onCreate(state);web=new WebView(this);setContentView(web);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);web.setWebViewClient(new WebViewClient(){public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){Uri u=req.getUrl();if("https".equals(u.getScheme())&&"exchange.africandroid.world".equals(u.getHost()))return false;if("https".equals(u.getScheme()))startActivity(new Intent(Intent.ACTION_VIEW,u));return true;}});web.loadUrl("https://exchange.africandroid.world/");}
 @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
}
