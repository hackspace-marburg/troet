{ config, lib, pkgs, ... }:

with lib;

let
    troet = pkgs.python310.pkgs.buildPythonPackage {
      pname = "troet";
      version = "0.0.1";

      src = lib.cleanSource ../../.;

      propagatedBuildInputs = with pkgs.python310Packages; [ sopel mastodon-py ];

      meta = {
        homepage = "https://github.com/hackspace-marburg/troet";
        description = "Mastodon plugin for Sopel IRC bots";
      };

      installPhase = ''
        mkdir -p $out/lib/sopel_modules
        cp -r $src/sopel_modules/troet $out/lib/sopel_modules
      '';

      doCheck = false;

    };

    mySopelNew = pkgs.python310.withPackages (p: with p; [ sopel mastodon-py troet ]);

    troet-uid = 9161;

    troetConfig = pkgs.writeText "sopel-config.yaml" ''
      [core]
      nick = ${cfg.core.nick}
      user = ${cfg.core.nick}
      name = ${cfg.core.nick}
      host = ${cfg.core.host}
      use_ssl = ${toString cfg.core.useSsl}
      port = ${toString cfg.core.port}
      owner = ${cfg.core.owner}
      channels =
        "${cfg.core.channel}"
      auth_method = sasl
      auth_username = ${cfg.core.nick}
      auth_password = ${cfg.core.authPassword}
      auth_target = PLAIN
      logdir = /var/log/troet
      pid_dir = /var/lib/troet/pid
      db_type = sqlite
      db_filename = /var/lib/troet/db
      exclude =
        xkcd
        adminchannel
        announce
        bugzilla
        calc
        choose
        clock
        countdown
        currency
        dice
        emoticons
        find
        invite
        ip
        isup
        lmgtfy
        meetbot
        ping
        pronouns
        py
        rand
        reddit
        reload
        remind
        safety
        search
        seen
        tell
        tld
        translate
        units
        uptime
        url
        version
        wikipedia
        wiktionary
      enable =
        troet

      extra = 
        ${troet}/lib/sopel_modules/troet

      [mastodon]
      id = ${cfg.mastodon.id}
      secret = ${cfg.mastodon.secret}
      token = ${cfg.mastodon.token}
      base_url = ${cfg.mastodon.baseUrl}
      notification_channel = ${cfg.mastodon.notificationChannel} 
    '';

    cfg = config.services.troet;

in {
  options.services.troet = {
    enable = mkEnableOption "troet";

    core.nick = mkOption {
      default = "troet";
      type = types.str;
    };

    core.host = mkOption {
      type = types.str;
    };

    core.useSsl = mkOption {
      type = types.bool;
    };

    core.port = mkOption {
      type = types.port;
    };

    core.owner = mkOption {
      type = types.str;
    };

    core.channel = mkOption {
      type = types.str;
    };

    core.authPassword = mkOption {
      type = types.str;
    };

    mastodon.id = mkOption {
      type = types.str;
    };

    mastodon.secret = mkOption {
      type = types.str;
    };

    mastodon.token = mkOption {
      type = types.str;
    };

    mastodon.baseUrl = mkOption {
      type = types.str;
    };

    mastodon.notificationChannel = mkOption {
      type = types.str;
    };

  };

  config = mkIf cfg.enable {
    systemd.services.troet = {
      description = "troet";

      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        ExecStart = ''
          ${mySopelNew}/bin/sopel \
            -c ${troetConfig}
        '';

        Type = "simple";

        User = "troet";
        Group = "troet";
      };
    };

    users.users.troet = {
      group = "troet";
      createHome = true;
      uid = troet-uid;
    };

    users.groups.troet.gid = troet-uid;

  };

}
