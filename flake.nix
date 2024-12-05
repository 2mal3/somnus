{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { self
    , nixpkgs
    ,
    }:
    let
      pkgs = nixpkgs.legacyPackages."x86_64-linux";
    in
    {
      devShells."x86_64-linux".default = pkgs.mkShell {
        packages = with pkgs; [
          rye
          openssl

          python311
          python311Packages.discordpy
          python311Packages.python-dotenv
          python311Packages.wakeonlan
          python311Packages.ping3
          python311Packages.pexpect
          python311Packages.mcstatus
          python311Packages.pydantic
          python311Packages.aiofiles
        ];
      };
    };
}
