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
      pkgs = import nixpkgs {
        inherit system;
      };
      treefmtEval = treefmt-nix.lib.evalModule pkgs ./treefmt.nix;

      python-script = pkgs.python311Packages.buildPythonApplication {
        pname = "matrix-mqtt-bridge";
        version = "0.1";
        doCheck = false;
        src = ./.;
        propagatedBuildInputs = with pkgs; [
          python311Packages.paho-mqtt
          python311Packages.matrix-nio
          python311Packages.configparser
        ];
      };

      containerImage = pkgs.dockerTools.buildLayeredImage {
        name = "ghcr.io/rubenhoenle/matrix-mqtt-bridge";
        tag = "unstable";
        contents = with pkgs; [ cacert coreutils bashInteractive iputils curl ];
        config = {
          Entrypoint = [ "${python-script}/bin/matrix_mqtt_bridge.py" ];
          Env = [ "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt" "PYTHONUNBUFFERED=1" ];
        };
      };
    in
    {
      formatter.${system} = treefmtEval.config.build.wrapper;
      checks.${system}.formatter = treefmtEval.config.build.check self;

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          python311
          python311Packages.paho-mqtt
          python311Packages.matrix-nio
          python311Packages.configparser
          python311Packages.python-dotenv
        ];
      };

      packages.${system} = {
        default = pkgs.writeShellScriptBin "matrix-mqtt-bridge" ''
          ${python-script}/bin/matrix_mqtt_bridge.py "''${@:1}"
        '';
        containerImage = containerImage;
      };
    };
}
