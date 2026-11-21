import {sha256Bytes} from "./package-manager.mjs";

const fail=code=>{throw new Error(code);};
const exact=(v,keys)=>!!v&&typeof v==="object"&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const validId=v=>typeof v==="string"&&/^[a-z][a-z0-9-]{0,47}$/.test(v)&&!["constructor","prototype"].includes(v);
const validVersion=v=>typeof v==="string"&&v.length<=32&&/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(v)&&v.split(".").every(x=>Number.isSafeInteger(Number(x)));
const validHash=v=>typeof v==="string"&&/^[0-9a-f]{64}$/.test(v);
const validKeyId=validHash;
const validTime=v=>Number.isSafeInteger(v)&&v>=0;
const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const encode64=bytes=>{
  let out="";
  for(let i=0;i<bytes.length;i+=3){
    const a=bytes[i],hasB=i+1<bytes.length,hasC=i+2<bytes.length,b=hasB?bytes[i+1]:0,c=hasC?bytes[i+2]:0;
    out+=alphabet[a>>2]+alphabet[((a&3)<<4)|(b>>4)]+(hasB?alphabet[((b&15)<<2)|(c>>6)]:"=")+(hasC?alphabet[c&63]:"=");
  }
  return out;
};
const decode64=value=>{
  if(typeof value!=="string"||value.length===0||value.length%4!==0||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))fail("INVALID_BASE64");
  const out=[];
  for(let i=0;i<value.length;i+=4){
    const a=alphabet.indexOf(value[i]),b=alphabet.indexOf(value[i+1]),c=value[i+2]==="="?0:alphabet.indexOf(value[i+2]),d=value[i+3]==="="?0:alphabet.indexOf(value[i+3]);
    out.push((a<<2)|(b>>4));
    if(value[i+2]!=="=")out.push(((b&15)<<4)|(c>>2));
    if(value[i+3]!=="=")out.push(((c&3)<<6)|d);
  }
  const bytes=Uint8Array.from(out);
  if(encode64(bytes)!==value)fail("INVALID_BASE64");
  return bytes;
};
const utf8=value=>new TextEncoder().encode(value);
const certPayload=c=>utf8([
  "MMS-EXT-KEY-CERT-V1",
  "issuer="+c.issuerKeyId,
  "subject="+c.subjectKeyId,
  "publicKey="+c.publicKey,
  "notBefore="+c.notBefore,
  "notAfter="+c.notAfter,
  "packageScopes="+c.packageScopes.join(","),
  ""
].join("\n"));
const revocationPayload=r=>utf8([
  "MMS-EXT-KEY-REVOCATION-V1",
  "issuer="+r.issuerKeyId,
  "target="+r.targetKeyId,
  "revokedAt="+r.revokedAt,
  "reason="+r.reasonCode,
  ""
].join("\n"));
const packagePayload=sig=>utf8([
  "MMS-EXT-PACKAGE-SIGNATURE-V1",
  "format=mmse-1",
  "packageId="+sig.packageId,
  "version="+sig.version,
  "archiveSha256="+sig.archiveSha256,
  "keyId="+sig.keyId,
  ""
].join("\n"));
const reasons=new Set(["COMPROMISED","ROTATED","RETIRED","POLICY_VIOLATION"]);
const validateScopes=scopes=>{
  if(!Array.isArray(scopes)||scopes.length<1||scopes.length>128||scopes.some(x=>!validId(x)))fail("INVALID_PACKAGE_SCOPES");
  const sorted=[...new Set(scopes)].sort();
  if(sorted.length!==scopes.length||sorted.some((x,i)=>x!==scopes[i]))fail("NON_CANONICAL_PACKAGE_SCOPES");
  return sorted;
};

export const createPublisherTrust=({trustRoots,cryptoProvider=globalThis.crypto,hashBytes=sha256Bytes}={})=>{
  if(!Array.isArray(trustRoots)||trustRoots.length<1||trustRoots.length>32)fail("TRUST_ROOTS_REQUIRED");
  const subtle=()=>{const s=cryptoProvider?.subtle;if(!s||typeof s.importKey!=="function"||typeof s.verify!=="function"||typeof s.sign!=="function")fail("WEBCRYPTO_UNAVAILABLE");return s;};
  const roots=new Map();
  for(const root of trustRoots){
    if(!exact(root,["keyId","publicKey","packageScopes"])||!validKeyId(root.keyId)||!(root.publicKey instanceof Uint8Array)||root.publicKey.length!==32)fail("INVALID_TRUST_ROOT");
    validateScopes(root.packageScopes);
    if(roots.has(root.keyId))fail("DUPLICATE_TRUST_ROOT");
    roots.set(root.keyId,{keyId:root.keyId,publicKey:root.publicKey.slice(),packageScopes:[...root.packageScopes]});
  }
  const nowSeconds=now=>now===undefined?Math.floor(Date.now()/1000):validTime(now)?now:fail("INVALID_TIME");
  const publicKeyId=async bytes=>{
    if(!(bytes instanceof Uint8Array)||bytes.length!==32)fail("INVALID_PUBLIC_KEY");
    return hashBytes(bytes);
  };
  const rootFor=async keyId=>{
    const root=roots.get(keyId);if(!root)fail("UNTRUSTED_ISSUER");
    if(await publicKeyId(root.publicKey)!==root.keyId)fail("TRUST_ROOT_KEY_ID_MISMATCH");
    return root;
  };
  const importVerifyKey=async raw=>{
    if(!(raw instanceof Uint8Array)||raw.length!==32)fail("INVALID_PUBLIC_KEY");
    try{return await subtle().importKey("raw",raw,{name:"Ed25519"},false,["verify"]);}catch{fail("ED25519_IMPORT_FAILED");}
  };
  const sign=async(privateKey,payload)=>{
    if(!privateKey)fail("PRIVATE_KEY_REQUIRED");
    try{return new Uint8Array(await subtle().sign({name:"Ed25519"},privateKey,payload));}catch{fail("ED25519_SIGN_FAILED");}
  };
  const verify=async(publicKey,signature,payload)=>{
    if(!(signature instanceof Uint8Array)||signature.length!==64)fail("INVALID_SIGNATURE_BYTES");
    const key=await importVerifyKey(publicKey);
    try{if(!await subtle().verify({name:"Ed25519"},key,signature,payload))fail("SIGNATURE_INVALID");}catch(e){if(e?.message==="SIGNATURE_INVALID")throw e;fail("ED25519_VERIFY_FAILED");}
    return true;
  };
  const assertRootScope=(root,scopes)=>{
    for(const id of scopes)if(!root.packageScopes.includes(id))fail("ROOT_SCOPE_EXCEEDED");
  };
  const createKeyCertificate=async({issuerKeyId,subjectPublicKey,notBefore,notAfter,packageScopes,issuerPrivateKey}={})=>{
    if(!validKeyId(issuerKeyId))fail("INVALID_ISSUER_KEY_ID");
    const root=await rootFor(issuerKeyId),scopes=validateScopes(packageScopes),start=nowSeconds(notBefore),end=nowSeconds(notAfter);
    if(start>=end)fail("INVALID_CERTIFICATE_VALIDITY");
    assertRootScope(root,scopes);
    const subjectKeyId=await publicKeyId(subjectPublicKey),unsigned={schema:1,algorithm:"Ed25519",issuerKeyId,subjectKeyId,publicKey:encode64(subjectPublicKey),notBefore:start,notAfter:end,packageScopes:scopes};
    return {...unsigned,signature:encode64(await sign(issuerPrivateKey,certPayload(unsigned)))};
  };
  const verifyCertificate=async(certificate,{packageId,now}={})=>{
    if(!exact(certificate,["schema","algorithm","issuerKeyId","subjectKeyId","publicKey","notBefore","notAfter","packageScopes","signature"])||certificate.schema!==1||certificate.algorithm!=="Ed25519")fail("INVALID_KEY_CERTIFICATE");
    if(!validKeyId(certificate.issuerKeyId)||!validKeyId(certificate.subjectKeyId))fail("INVALID_KEY_ID");
    if(!validTime(certificate.notBefore)||!validTime(certificate.notAfter)||certificate.notBefore>=certificate.notAfter)fail("INVALID_CERTIFICATE_VALIDITY");
    const current=nowSeconds(now);if(current<certificate.notBefore)fail("CERTIFICATE_NOT_YET_VALID");if(current>=certificate.notAfter)fail("CERTIFICATE_EXPIRED");
    const scopes=validateScopes(certificate.packageScopes);
    if(packageId!==undefined&&(!validId(packageId)||!scopes.includes(packageId)))fail("PACKAGE_OUTSIDE_CERTIFICATE_SCOPE");
    const root=await rootFor(certificate.issuerKeyId);assertRootScope(root,scopes);
    const publicKey=decode64(certificate.publicKey),signature=decode64(certificate.signature);
    if(await publicKeyId(publicKey)!==certificate.subjectKeyId)fail("SUBJECT_KEY_ID_MISMATCH");
    await verify(root.publicKey,signature,certPayload(certificate));
    return {keyId:certificate.subjectKeyId,issuerKeyId:certificate.issuerKeyId,publicKey,packageScopes:scopes,notBefore:certificate.notBefore,notAfter:certificate.notAfter};
  };
  const createRevocation=async({issuerKeyId,targetKeyId,revokedAt,reasonCode,issuerPrivateKey}={})=>{
    if(!validKeyId(issuerKeyId)||!validKeyId(targetKeyId))fail("INVALID_KEY_ID");
    await rootFor(issuerKeyId);const time=nowSeconds(revokedAt);
    if(!reasons.has(reasonCode))fail("INVALID_REVOCATION_REASON");
    const unsigned={schema:1,algorithm:"Ed25519",issuerKeyId,targetKeyId,revokedAt:time,reasonCode};
    return {...unsigned,signature:encode64(await sign(issuerPrivateKey,revocationPayload(unsigned)))};
  };
  const verifyRevocation=async(r)=>{
    if(!exact(r,["schema","algorithm","issuerKeyId","targetKeyId","revokedAt","reasonCode","signature"])||r.schema!==1||r.algorithm!=="Ed25519")fail("INVALID_REVOCATION");
    if(!validKeyId(r.issuerKeyId)||!validKeyId(r.targetKeyId)||!validTime(r.revokedAt)||!reasons.has(r.reasonCode))fail("INVALID_REVOCATION");
    const root=await rootFor(r.issuerKeyId);
    await verify(root.publicKey,decode64(r.signature),revocationPayload(r));
    return r;
  };
  const createPackageSignature=async({archiveBytes,manifest,keyId,privateKey}={})=>{
    if(!(archiveBytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
    if(!manifest||!validId(manifest.id)||!validVersion(manifest.version)||!validKeyId(keyId))fail("INVALID_PACKAGE_IDENTITY");
    const unsigned={schema:1,algorithm:"Ed25519",keyId,packageId:manifest.id,version:manifest.version,archiveSha256:hashBytes(archiveBytes)};
    return {...unsigned,signature:encode64(await sign(privateKey,packagePayload(unsigned)))};
  };
  const verifyPackageSignature=async({archiveBytes,manifest,signature,certificate,revocations=[],now}={})=>{
    if(!(archiveBytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
    if(!manifest||!validId(manifest.id)||!validVersion(manifest.version))fail("INVALID_PACKAGE_IDENTITY");
    if(!exact(signature,["schema","algorithm","keyId","packageId","version","archiveSha256","signature"])||signature.schema!==1||signature.algorithm!=="Ed25519")fail("INVALID_PACKAGE_SIGNATURE");
    if(!validKeyId(signature.keyId)||!validId(signature.packageId)||!validVersion(signature.version)||!validHash(signature.archiveSha256))fail("INVALID_PACKAGE_SIGNATURE");
    if(signature.packageId!==manifest.id||signature.version!==manifest.version)fail("PACKAGE_IDENTITY_MISMATCH");
    const digest=hashBytes(archiveBytes);if(signature.archiveSha256!==digest)fail("ARCHIVE_DIGEST_MISMATCH");
    const cert=await verifyCertificate(certificate,{packageId:manifest.id,now});
    if(signature.keyId!==cert.keyId)fail("SIGNER_CERTIFICATE_MISMATCH");
    if(!Array.isArray(revocations)||revocations.length>256)fail("INVALID_REVOCATION_LIST");
    const current=nowSeconds(now);
    for(const r of revocations){
      await verifyRevocation(r);
      if(r.targetKeyId===cert.keyId&&r.issuerKeyId===cert.issuerKeyId&&r.revokedAt<=current)fail("SIGNING_KEY_REVOKED");
    }
    await verify(cert.publicKey,decode64(signature.signature),packagePayload(signature));
    return {trusted:true,keyId:cert.keyId,issuerKeyId:cert.issuerKeyId,packageId:manifest.id,version:manifest.version,archiveSha256:digest};
  };
  return {publicKeyId,createKeyCertificate,verifyCertificate,createRevocation,verifyRevocation,createPackageSignature,verifyPackageSignature};
};
