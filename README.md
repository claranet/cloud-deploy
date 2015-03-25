- Necessite une version de Fabric >= 1.10.1 (Bug encoding fixed)

JOB
{
	command: "deploy",
	parameters: [options: "hard", app_id: APPLICATION_ID, modules: [name: "php5", rev: "staging"]],
	status: "launched"
}

APP
{
	"aws_region" : "us-east-1",
	//"bucket_s3" : "s3://deploy-811874869762", Auto déterminé nom_appli_env_arnid_deploy
	"modules": [{"name": "code_wbb", "git_repo": "github.com/***REMOVED***.git", "code_deploy": {}, "build_pack": "SCRIPTSHELL ou fichier Git"}] // code deploy AppSpec definition
	],
	"env": "staging",
	"features": [{"name": "php5-fpm", "version": "5.5"}, {"name": "nginx", "version": "1.4.2"], // version optionnel, name = SaltStack state
	"role" : "webserver",
	"name" : "worldsbestbars", // vérifier characteres lowercase [a-z][0-9]
	"log_notifications" : [
		"ingenieurs@morea.fr",
		"wbb-notification@void.fr"
	],
	"ami": "ami_id", // Stored by Packer
	"instance_type": "t2.small"
	"autoscale": {"min": 1, "max": 2, "current": 1}
}


./bootstrap.sh :
- Changement hostname pour Zabbix
- Changement DNS dans route 53 privé

Gestion des rôles par ressources OK
- superadmin (Morea) (ALL)
- admin (Client Dev) (Tout sauf : rebuild_image, DELETE)
- user (Client) (RO)
Peut-on définir un rôle sur une subresources ex : JOB: {command : rebuild_image}
