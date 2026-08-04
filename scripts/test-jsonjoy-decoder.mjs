#!/usr/bin/env node
/**
 * Test script to verify @jsonjoy.com/json-pack can decode the problematic SLP footer.
 */
const fs = require('fs');

async function test() {
  try {
    const { createUbjsonDecoder } = await import('@jsonjoy.com/json-pack');
    
    const filepath = '/home/agiera/Downloads/20120130T074801Z_babs-919_vs_p2_s28_7d33dfbe.slp';
    const data = fs.readFileSync(filepath);
    
    console.log(`File: ${filepath}`);
    console.log(`Size: ${data.length} bytes\n`);
    
    // Extract footer (starts at last {{ pattern or metadata offset)
    const footerStart = 1602345;
    const footer = Buffer.from(data.buffer, footerStart, data.length - footerStart - 4);
    
    console.log(`Footer size: ${footer.length} bytes`);
    console.log(`Footer start (hex): ${footer.slice(0, 50).toString('hex')}\n`);
    
    // Test decoding
    console.log('Attempting to decode with @jsonjoy.com/json-pack...');
    const decoder = createUbjsonDecoder();
    const result = decoder.decode(footer);
    
    console.log('✓ Successfully decoded footer!');
    console.log('Result:', JSON.stringify(result, null, 2));
    
  } catch (err) {
    console.error('✗ Decoding failed:');
    console.error(err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

test();
