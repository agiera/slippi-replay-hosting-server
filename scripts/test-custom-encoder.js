/**
 * Test the custom UBJSON encoder to verify output format
 */

// Simulate the custom encoder
function encodeControllerMetadata(obj) {
  const buf = [];
  
  // Start object
  buf.push(0x7b); // {
  
  // Sort keys for deterministic output
  const keys = Object.keys(obj).sort();
  
  for (const key of keys) {
    const value = String(obj[key]); // Coerce to string
    
    // Encode key
    const keyBytes = Buffer.from(key, 'utf8');
    if (keyBytes.length > 255) {
      throw new Error(`UBJSON key too long: "${key}" (${keyBytes.length} bytes, max 255)`);
    }
    buf.push(0x53); // S marker
    buf.push(0x69); // i marker
    buf.push(keyBytes.length);
    buf.push(...keyBytes);
    
    // Encode value
    const valBytes = Buffer.from(value, 'utf8');
    if (valBytes.length > 255) {
      throw new Error(`UBJSON value too long for key "${key}": "${value}" (${valBytes.length} bytes, max 255)`);
    }
    buf.push(0x53); // S marker
    buf.push(0x69); // i marker
    buf.push(valBytes.length);
    buf.push(...valBytes);
  }
  
  // End object
  buf.push(0x7d); // }
  
  return Buffer.from(buf);
}

// Test data
const singleController = {
  nametag: 'HC',
  name: 'Player',
  slippi: 'HC#001',
  smashgg: 'user-123',
  parrygg: 'parry-456',
  firmware: '1.2.3'
};

const encoded = encodeControllerMetadata(singleController);

console.log('=== CUSTOM UBJSON ENCODER OUTPUT ===');
console.log('Hex:', encoded.toString('hex'));
console.log('Length:', encoded.length);
console.log('');
console.log('Full byte breakdown:');
let hex = '';
for (let i = 0; i < encoded.length; i++) {
  const b = encoded[i];
  const hexStr = b.toString(16).padStart(2, '0');
  let marker = '';
  
  if (b === 0x7b) marker = ' { start';
  else if (b === 0x7d) marker = ' } end';
  else if (b === 0x53) marker = ' S string';
  else if (b === 0x69) marker = ' i uint8_len';
  else if (b >= 0x20 && b < 0x7f) marker = ' "' + String.fromCharCode(b) + '"';
  
  console.log('0x' + hexStr + marker);
}
