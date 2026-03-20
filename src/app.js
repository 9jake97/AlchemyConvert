/**
 * AlchemyConvert - Cleaned & Deobfuscated App Logic
 * Added: Selective Item Conversion
 */

const fs = require('fs');
const path = require('path');
const { spawn, exec } = require('child_process');
let JSZip;
try {
    JSZip = require('jszip');
} catch (e) {
    JSZip = window.JSZip; // Fallback to CDN version from index.html
}

// UI Elements
const batchLog = document.getElementById('batchLog');
const batchStatus = document.getElementById('batchStatus');
const zipInput = document.getElementById('zipInput');
const itemSelectionContainer = document.getElementById('itemSelectionContainer');
const itemListDiv = document.getElementById('itemList');
const itemSearch = document.getElementById('itemSearch');
const selectAllBtn = document.getElementById('selectAllItems');
const deselectAllBtn = document.getElementById('deselectAllItems');
const startSelectionBtn = document.getElementById('startSelectionBtn');

let isProcessing = false;
let indexedTextures = {}; // Maps name/path to JSZip Entry
let allDiscoveredModels = []; 
let currentZipFile = null;

// Log function
function log(msg) {
    batchLog.textContent += msg + '\n';
    batchLog.scrollTop = batchLog.scrollHeight;
}

// Main File Change Listener
zipInput.addEventListener('change', async (e) => {
    if (e.target.files.length > 0) {
        currentZipFile = e.target.files[0];
        await indexZipFile(currentZipFile);
    }
});

async function indexZipFile(file) {
    if (isProcessing) return;
    
    batchLog.textContent = '';
    batchStatus.textContent = '📦 Reading ZIP...';
    itemSelectionContainer.style.display = 'none';
    log(`Reading ZIP: ${file.path || file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

    try {
        const zip = await JSZip.loadAsync(file);
        const jsonEntries = [];
        indexedTextures = {};
        
        // Scan for models and textures
        zip.forEach((relPath, entry) => {
            if (entry.dir) return;
            const normalizedPath = relPath.replace(/\\/g, '/').toLowerCase();
            
            if (normalizedPath.endsWith('.json')) {
                jsonEntries.push({ path: relPath, entry: entry });
            } else if (normalizedPath.endsWith('.png')) {
                const name = relPath.split('/').pop().replace(/\.png$/i, '');
                indexedTextures[normalizedPath.replace(/\.png$/i, '')] = entry;
                if (!indexedTextures[name]) indexedTextures[name] = entry;
                
                // Texture folder relative path
                const texIdx = normalizedPath.indexOf('/textures/');
                if (texIdx !== -1) {
                    const relTexPath = normalizedPath.substring(texIdx + 10).replace(/\.png$/i, '');
                    indexedTextures[relTexPath] = entry;
                }
            }
        });

        // Filter models
        const skipDirs = ['assets/betterhud', 'assets/modelengine', 'assets/minecraft/models/block', 'assets/nameplates'];
        const skipFiles = ['_charged', '_cosmetic', '_cast', '_normal'];

        allDiscoveredModels = jsonEntries.filter(model => {
            const lPath = model.path.toLowerCase();
            if (skipDirs.some(d => lPath.includes(d))) return false;
            
            const fileName = lPath.split('/').pop().replace(/\.json$/i, '');
            if (skipFiles.some(f => fileName.includes(f))) return false;
            
            return true;
        });

        log(`Found ${allDiscoveredModels.length} candidate models.`);
        console.log("Discovered models:", allDiscoveredModels);
        
        if (allDiscoveredModels.length > 0) {
            showItemSelection();
        } else {
            batchStatus.textContent = '❌ No valid models found in ZIP.';
        }

    } catch (err) {
        log(`Error indexing ZIP: ${err.message}`);
        console.error(err);
    }
}

function showItemSelection() {
    itemSelectionContainer.style.display = 'block';
    populateItemList(allDiscoveredModels);
    batchStatus.textContent = '🔍 Select items below to convert.';
}

function populateItemList(models) {
    itemListDiv.innerHTML = '';
    models.forEach((model, index) => {
        const name = model.path.split('/').pop().replace(/\.json$/i, '');
        const row = document.createElement('div');
        row.className = 'item-row';
        row.innerHTML = `
            <input type="checkbox" id="item_${index}" value="${index}" checked>
            <label for="item_${index}" title="${model.path}">${name}</label>
        `;
        itemListDiv.appendChild(row);
    });
}

// Selection Controls
selectAllBtn.addEventListener('click', () => {
    itemListDiv.querySelectorAll('.item-row:not([style*="display: none"]) input').forEach(cb => cb.checked = true);
});

deselectAllBtn.addEventListener('click', () => {
    itemListDiv.querySelectorAll('.item-row:not([style*="display: none"]) input').forEach(cb => cb.checked = false);
});

itemSearch.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    itemListDiv.querySelectorAll('.item-row').forEach(row => {
        const name = row.querySelector('label').textContent.toLowerCase();
        row.style.display = name.includes(term) ? 'flex' : 'none';
    });
});

startSelectionBtn.addEventListener('click', async () => {
    const selectedIndices = Array.from(itemListDiv.querySelectorAll('input:checked')).map(cb => parseInt(cb.value));
    if (selectedIndices.length === 0) {
        alert('Please select at least one item!');
        return;
    }
    
    const selectedModels = selectedIndices.map(idx => allDiscoveredModels[idx]);
    itemSelectionContainer.style.display = 'none';
    await runConversion(selectedModels);
});

async function runConversion(modelsToConvert) {
    isProcessing = true;
    batchLog.textContent = '';
    batchStatus.textContent = '🔄 Generating Icons...';
    log(`Starting selective conversion of ${modelsToConvert.length} items.`);
    console.log("Selective conversion started:", modelsToConvert);
    viewer.removeAll();

    const total = modelsToConvert.length;
    let successCount = 0;
    
    // Preparation for icons
    const iconZip = new JSZip();
    const iconBase = iconZip.folder('textures').folder('zicon');

    // Root Working Dir
    let workingDir = __dirname;
    if (workingDir.includes('app.asar')) workingDir = workingDir.replace('app.asar', 'app.asar.unpacked');
    const convertRPDir = path.join(workingDir, 'ConvertRP');

    for (let i = 0; i < total; i++) {
        const modelInfo = modelsToConvert[i];
        const modelName = modelInfo.path.split('/').pop().replace(/\.json$/i, '');
        batchStatus.textContent = `Rendering ${i+1}/${total}: ${modelName}`;

        try {
            const content = await modelInfo.entry.async('string');
            const data = JSON.parse(content);
            
            // Texture Resolution logic
            const resolvedTextures = [];
            if (data.textures) {
                for (const [key, texPath] of Object.entries(data.textures)) {
                    if (texPath.startsWith('#')) continue; // Skip variable pointers
                    
                    const nameOnly = texPath.split('/').pop();
                    const entry = indexedTextures[texPath] || indexedTextures[nameOnly];
                    
                    if (entry) {
                        const base64 = await entry.async('base64');
                        resolvedTextures.push({
                            name: nameOnly,
                            texture: 'data:image/png;base64,' + base64
                        });
                    }
                }
            }

            // Create Icon via ModelViewer
            // Note: We use the existing ModelViewer instance from the page
            viewer.clear();
            const model = new JsonModel(modelName, data, resolvedTextures, false);
            viewer.add(model);
            
            // Render and Snap
            await new Promise(r => requestAnimationFrame(r)); // Wait for render
            const canvas = viewer.renderer.domElement;
            const dataUrl = canvas.toDataURL('image/png');
            iconBase.file(modelName + '.png', dataUrl.split(',')[1], { base64: true });
            
            log(`✓ ${modelName}`);
            successCount++;
        } catch (err) {
            log(`✗ ${modelName}: ${err.message}`);
        }
    }

    // Write selected items list for Python filtering
    const selectedList = modelsToConvert.map(m => m.path.split('/').pop().replace(/\.json$/i, ''));
    fs.writeFileSync(path.join(convertRPDir, 'selected_items.json'), JSON.stringify(selectedList));

    log(`\nRendering complete. Pushing to Python converter...`);
    await callPythonConverter(currentZipFile.path || currentZipFile.name, convertRPDir);
    
    isProcessing = false;
    batchStatus.textContent = '✅ All steps complete!';
}

async function callPythonConverter(zipPath, dir) {
    return new Promise((resolve, reject) => {
        const pythonBin = path.join(dir, 'python_bin', 'python.exe');
        const script = path.join(dir, 'converter.py');
        const mappingVersion = document.getElementById('settingMappingVersion').value || 'v1';
        
        log(`Using script: ${script}`);
        
        const args = ['-u', script, zipPath, '--mapping_version', mappingVersion, '--filter', 'selected_items.json'];
        const process = spawn(pythonBin, args, { cwd: dir });

        process.stdout.on('data', data => log(`[Python] ${data.toString().trim()}`));
        process.stderr.on('data', data => log(`[Python Error] ${data.toString().trim()}`));
        
        process.on('close', code => {
            if (code === 0) {
                log('\nPython conversion successful!');
                resolve();
            } else {
                log(`\nPython process failed with code ${code}`);
                reject(new Error(`Exit code ${code}`));
            }
        });
    });
}