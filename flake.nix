{
  description = "Nocapture: a native Noctalia capture toolbar";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      project =
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          launcher = pkgs.writeShellApplication {
            name = "nocapture";
            runtimeInputs = [ pkgs.gnugrep ];
            text = builtins.readFile ./bin/nocapture;
          };
          package = pkgs.symlinkJoin {
            name = "nocapture";
            paths = [ launcher ];
            postBuild = ''
              mkdir -p "$out/share/noctalia/plugins"
              cp -r ${./nocapture} "$out/share/noctalia/plugins/nocapture"
              install -Dm644 ${./LICENSE} "$out/share/licenses/nocapture/LICENSE"
              test -s "$out/share/noctalia/plugins/nocapture/plugin.toml"
            '';
            meta = {
              description = "Capture toolbar for Noctalia and Niri";
              license = pkgs.lib.licenses.mit;
              platforms = systems;
              mainProgram = "nocapture";
            };
          };
          tools = [
            pkgs.bash
            pkgs.coreutils
            pkgs.gnugrep
            pkgs.lua5_4
            pkgs.stylua
            pkgs.shfmt
            pkgs.shellcheck
            pkgs.nixfmt
          ];
          app = name: text: {
            type = "app";
            meta.description = "Nocapture development command: ${name}";
            program = pkgs.lib.getExe (
              pkgs.writeShellApplication {
                inherit name text;
                runtimeInputs = tools;
              }
            );
          };
          check = ''
            nixfmt --check flake.nix
            stylua --check nocapture tests/*.lua
            shfmt -i 2 -d bin/nocapture tests/cli.sh
            shellcheck bin/nocapture tests/cli.sh
            lua tests/run.lua
            bash tests/cli.sh
          '';
        in
        {
          inherit
            pkgs
            package
            tools
            app
            check
            ;
        };
    in
    {
      packages = forAllSystems (system: {
        default = (project system).package;
      });
      apps = forAllSystems (
        system:
        let
          p = project system;
        in
        {
          default = {
            type = "app";
            meta.description = "Open the Nocapture toolbar in Noctalia";
            program = nixpkgs.lib.getExe p.package;
          };
          dev = p.app "nocapture-dev" ''exec bash bin/nocapture "$@"'';
          test = p.app "nocapture-test" ''lua tests/run.lua "$@"; bash tests/cli.sh'';
          check = p.app "nocapture-check" p.check;
          fmt = p.app "nocapture-fmt" ''
            stylua nocapture tests/*.lua
            shfmt -i 2 -w bin/nocapture tests/cli.sh
            nixfmt flake.nix
          '';
        }
      );
      devShells = forAllSystems (
        system:
        let
          p = project system;
        in
        {
          default = p.pkgs.mkShell { packages = p.tools ++ [ p.package ]; };
        }
      );
      formatter = forAllSystems (system: (project system).pkgs.nixfmt);
      checks = forAllSystems (
        system:
        let
          p = project system;
        in
        {
          package = p.package;
          unit = p.pkgs.runCommand "nocapture-check" { nativeBuildInputs = p.tools; } ''
            cp -r ${self} source
            chmod -R u+w source
            cd source
            ${p.check}
            touch "$out"
          '';
        }
      );
    };
}
