import assert from 'node:assert/strict';
// Uses existing browser tooling; does not install a dependency.
const {chromium} = await import(process.env.PAPER_BROWSER_MODULE || 'playwright-core');
const browserPath = process.env.PAPER_BROWSER_PATH || '/usr/bin/chromium';
const previewUrl = process.env.PAPER_UI_BASE_URL || 'http://localhost:5173';
const browser=await chromium.launch({executablePath:browserPath,headless:true});
try {
 for(const width of [1440,1024,390,320]){
  const context=await browser.newContext({viewport:{width,height:844}});const page=await context.newPage();
  await page.goto(previewUrl + '/results');await page.locator('.pf-shell').waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  if(width>=1280){await page.getByRole('button',{name:'Collapse navigation',exact:true}).click();assert.equal(await page.locator('.pf-sidebar').evaluate(n=>n.getBoundingClientRect().width),64);}
  else {await page.getByRole('button',{name:'Open navigation',exact:true}).click();
   for(let i=0;i<22;i++){await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>!!document.activeElement.closest('#navigation-dialog')),true);}
   for(let i=0;i<22;i++){await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>!!document.activeElement.closest('#navigation-dialog')),true);}
   await page.keyboard.press('Escape');assert.equal(await page.locator('dialog').isVisible(),false);
   assert.equal(await page.getByRole('button',{name:'Open navigation',exact:true}).evaluate(n=>n===document.activeElement),true);
  }
  await page.getByRole('button',{name:'Switch to dark mode',exact:true}).click();assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('dark')),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  console.log(`OK ${width}px layout, navigation, theme and keyboard behavior`);await context.close();
 }
}finally{await browser.close();}
