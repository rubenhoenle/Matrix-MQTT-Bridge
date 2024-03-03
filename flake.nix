{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, treefmt-nix }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      treefmtEval = treefmt-nix.lib.evalModule pkgs ./treefmt.nix;
      matrixbridge = pkgs.buildGoModule {
        pname = "matrix-bridge";
        version = "1.0.0";
        vendorHash = null;
        src = ./.;
      };
    in
    {
      formatter.${system} = treefmtEval.config.build.wrapper;
      checks.${system}.formatter = treefmtEval.config.build.check self;

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs;[
          go
        ];
      };
      packages.${system} = {
        default = matrixbridge;
        #lack-dev = pkgs.writeScriptBin "lacksbuttern" ''${lacksbuttern}/bin/lacksbuttern -type lack -address 127.0.0.1:8080'';
      };
    };
}
