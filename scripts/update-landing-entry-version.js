const { readFileSync, writeFileSync } = require('fs');
const { join } = require('path');

const projectRoot = __dirname ? join(__dirname, '..') : '..';

const htmlPath = join(projectRoot, 'static', 'landing.html');
const entryPath = join(projectRoot, 'static', 'landing.entry.js');

const version = Date.now().toString();

const replaceVersion = (content, resource) => {
  const pattern = new RegExp(`${resource}\\?v=\\d+`, 'g');
  if (!pattern.test(content)) {
    return content;
  }
  return content.replace(pattern, `${resource}?v=${version}`);
};

try {
  const entryContent = readFileSync(entryPath, 'utf8');
  const updatedEntry = replaceVersion(entryContent, '/static/landing.bundle.js');
  if (entryContent !== updatedEntry) {
    writeFileSync(entryPath, updatedEntry, 'utf8');
  }

  const htmlContent = readFileSync(htmlPath, 'utf8');
  const updatedHtml = replaceVersion(htmlContent, '/static/landing.entry.js');
  if (htmlContent !== updatedHtml) {
    writeFileSync(htmlPath, updatedHtml, 'utf8');
  }

  console.log(`✅ landing assets version updated to ${version}`);
} catch (error) {
  console.error('Failed to update landing asset version:', error);
  process.exit(1);
}
