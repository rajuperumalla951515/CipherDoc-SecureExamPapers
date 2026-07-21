const crypto = require('crypto');
const fs = require('fs');

function generateRsaKeyPair() {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 2048,
    publicExponent: 0x10001,
    publicKeyEncoding: {
      type: 'spki',
      format: 'pem'
    },
    privateKeyEncoding: {
      type: 'pkcs8',
      format: 'pem'
    }
  });
  return { privatePem: privateKey, publicPem: publicKey };
}

function generateAesKey() {
  return crypto.randomBytes(32);
}

function encryptWithAesGcm(data, aesKey) {
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', aesKey, nonce);
  
  let ciphertext = cipher.update(data);
  ciphertext = Buffer.concat([ciphertext, cipher.final()]);
  const authTag = cipher.getAuthTag();
  
  // Prepend nonce, append auth tag to match python
  return Buffer.concat([nonce, ciphertext, authTag]);
}

function decryptWithAesGcm(encryptedData, aesKey) {
  const nonce = encryptedData.subarray(0, 12);
  const authTag = encryptedData.subarray(encryptedData.length - 16);
  const ciphertext = encryptedData.subarray(12, encryptedData.length - 16);
  
  const decipher = crypto.createDecipheriv('aes-256-gcm', aesKey, nonce);
  decipher.setAuthTag(authTag);
  
  let decrypted = decipher.update(ciphertext);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  
  return decrypted;
}

function encryptAesKeyWithRsa(aesKey, publicPem) {
  const encryptedKey = crypto.publicEncrypt({
    key: publicPem,
    padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
    oaepHash: 'sha256'
  }, aesKey);
  
  return encryptedKey.toString('base64');
}

function decryptAesKeyWithRsa(encryptedAesKeyB64, privatePem) {
  const encryptedAesKey = Buffer.from(encryptedAesKeyB64, 'base64');
  
  const aesKey = crypto.privateDecrypt({
    key: privatePem,
    padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
    oaepHash: 'sha256'
  }, encryptedAesKey);
  
  return aesKey;
}

function encryptFile(filePath, publicPem) {
  const fileData = fs.readFileSync(filePath);
  const aesKey = generateAesKey();
  
  const encryptedData = encryptWithAesGcm(fileData, aesKey);
  const encryptedAesKey = encryptAesKeyWithRsa(aesKey, publicPem);
  
  const encryptedFilePath = filePath + '.encrypted';
  fs.writeFileSync(encryptedFilePath, encryptedData);
  
  return { encryptedFilePath, encryptedAesKey };
}

function decryptFile(encryptedFilePath, encryptedAesKey, privatePem) {
  const aesKey = decryptAesKeyWithRsa(encryptedAesKey, privatePem);
  const encryptedData = fs.readFileSync(encryptedFilePath);
  
  const decryptedData = decryptWithAesGcm(encryptedData, aesKey);
  
  const decryptedFilePath = encryptedFilePath.replace('.encrypted', '.decrypted');
  fs.writeFileSync(decryptedFilePath, decryptedData);
  
  return { decryptedFilePath, decryptedData };
}

function encryptText(text, publicPem) {
  const aesKey = generateAesKey();
  const encryptedData = encryptWithAesGcm(Buffer.from(text, 'utf8'), aesKey);
  const encryptedAesKey = encryptAesKeyWithRsa(aesKey, publicPem);
  
  return { encryptedTextB64: encryptedData.toString('base64'), encryptedAesKey };
}

function decryptText(encryptedTextB64, encryptedAesKey, privatePem) {
  const aesKey = decryptAesKeyWithRsa(encryptedAesKey, privatePem);
  const encryptedData = Buffer.from(encryptedTextB64, 'base64');
  
  const decryptedData = decryptWithAesGcm(encryptedData, aesKey);
  return decryptedData.toString('utf8');
}

module.exports = {
  generateRsaKeyPair,
  generateAesKey,
  encryptWithAesGcm,
  decryptWithAesGcm,
  encryptAesKeyWithRsa,
  decryptAesKeyWithRsa,
  encryptFile,
  decryptFile,
  encryptText,
  decryptText
};
