const fs = require('fs');
const files = [
  'src/voice/VozToggle.tsx',
  'src/SimView.tsx',
  'src/LiveSimView.tsx',
  'src/sim/LiveControls.tsx',
  'src/sim/ShockBanner.tsx',
  'src/sim/Distribution.tsx',
  'src/sim/Decisions.tsx',
  'src/sim/DecisionHistory.tsx',
  'src/sim/Counters.tsx',
  'src/sim/Counterfactual.tsx',
  'src/map/route.ts'
];

files.forEach(f => {
  let content = fs.readFileSync(f, 'utf8');
  content = content.replace(/Nuez voice/g, 'Navie voice');
  content = content.replace(/aria-label="Nuez"/g, 'aria-label="Navie"');
  content = content.replace(/\? 'Nuez'/g, '? \\'Navie\\'');
  content = content.replace(/Nuez consistently/g, 'Navie consistently');
  content = content.replace(/Nuez achieves/g, 'Navie achieves');
  content = content.replace(/>Nuez Decisions</g, '>Navie Decisions<');
  content = content.replace(/Why Nuez skipped/g, 'Why Navie skipped');
  content = content.replace(/>Nuez</g, '>Navie<');
  content = content.replace(/Nuez \${diffSign}/g, 'Navie ${diffSign}');
  content = content.replace(/>Nuez total</g, '>Navie total<');
  content = content.replace(/If Nuez had/g, 'If Navie had');
  content = content.replace(/Nuez IA/g, 'Navie IA');
  
  fs.writeFileSync(f, content);
});
console.log('Replaced Nuez with Navie in UI texts.');
