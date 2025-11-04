const { readFileSync, writeFileSync } = require('fs');
const { join } = require('path');

const projectRoot = __dirname ? join(__dirname, '..') : '..';

const htmlPath = join(projectRoot, 'static', 'bank-reconciliation.html');
const entryPath = join(projectRoot, 'static', 'bank-reconciliation.entry.js');

const version = Date.now().toString();

const replaceVersion = (content, resourcePath) => {
  const pattern = new RegExp(`${resourcePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\?v=\\d+`, 'g');
  if (!pattern.test(content)) {
    return content;
  }
  return content.replace(pattern, `${resourcePath}?v=${version}`);
};

try {
  const entryContent = readFileSync(entryPath, 'utf8');
  const updatedEntry = replaceVersion(entryContent, '/static/bank-reconciliation.bundle.js');
  if (entryContent !== updatedEntry) {
    writeFileSync(entryPath, updatedEntry, 'utf8');
  }

  const htmlContent = readFileSync(htmlPath, 'utf8');
  const updatedHtml = replaceVersion(htmlContent, '/static/bank-reconciliation.entry.js');
  if (htmlContent !== updatedHtml) {
    writeFileSync(htmlPath, updatedHtml, 'utf8');
  }

  console.log(`✅ bank-reconciliation assets version updated to ${version}`);
} catch (error) {
  console.error('Failed to update bank reconciliation asset version:', error);
  process.exit(1);
}
