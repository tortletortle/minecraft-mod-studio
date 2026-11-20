// Orthographic isometric projection, camera rotate in 90-degree increments.
function projection(size,rotation,layer,viewport){
 const [w,h,d]=size,rot=((rotation%4)+4)%4, W=rot%2?d:w,D=rot%2?w:d;
 const ww=viewport[0],hh=viewport[1],margin=32;
 const a=Math.max(0.5,Math.min((ww-2*margin)/(W+D),(hh-2*margin)/((W+D)*.5+(layer+1)*1.15)));
 const b=a*.5,c=a*1.15;
 const ox=(ww-(W-D)*a)/2,oy=(hh-(W+D)*b+(layer+1)*c)/2;
 const turn=(x,z)=>rot===0?[x,z]:rot===1?[z,w-x]:rot===2?[w-x,d-z]:[d-z,x];
 const unturn=(u,v)=>rot===0?[u,v]:rot===1?[w-v,u]:rot===2?[w-u,d-v]:[v,d-u];
 const point=(x,y,z)=>{const [u,v]=turn(x,z);return [ox+(u-v)*a,oy+(u+v)*b-y*c];};
 const pick=(px,py,y)=>{const x=(px-ox)/a,z=(py-oy+y*c)/b;const [i,j]=unturn((x+z)/2,(z-x)/2);const ix=Math.floor(i+1e-9),iz=Math.floor(j+1e-9);return ix>=0&&ix<w&&iz>=0&&iz<d?[ix,iz]:null;};
 const depth=(x,y,z)=>{const [u,v]=turn(x+.5,z+.5);return u+v+y;};
 return {point,pick,depth,rotation:rot};
}
export {projection};
