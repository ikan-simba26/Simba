/** A picture imported by its path is its address in the build. */
declare module "*.svg" {
  const address: string;
  export default address;
}
