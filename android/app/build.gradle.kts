plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// 版本号集中在这里: versionCode/versionName、APK 文件名、dist 拷贝都用它
val appVersionCode = 20
val appVersionName = "2.9"
val apkBaseName = "MusicPlayer-android-v$appVersionName"

android {
    namespace = "com.musicplayer.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.musicplayer.app"
        minSdk = 29          // MediaStore RELATIVE_PATH/IS_PENDING 需要 API 29+
        targetSdk = 34
        versionCode = appVersionCode
        versionName = appVersionName
        ndk {
            // 覆盖绝大多数真机; 如需 32 位老设备可改用 Python 3.11 + armeabi-v7a
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// 产物名带上版本号: app-debug.apk → MusicPlayer-android-v2.5.apk
androidComponents {
    onVariants { variant ->
        variant.outputs.forEach { output ->
            (output as? com.android.build.api.variant.impl.VariantOutputImpl)
                ?.outputFileName?.set("$apkBaseName.apk")
        }
    }
}

// 一条命令出包并拷到 dist: gradle :app:distDebug
tasks.register<Copy>("distDebug") {
    dependsOn("assembleDebug")
    from(layout.buildDirectory.file("outputs/apk/debug/app-debug.apk")) {
        rename { "$apkBaseName.apk" }        // 兜底: 无论上面改名是否生效, dist 里都带版本号
    }
    from(layout.buildDirectory.file("outputs/apk/debug/$apkBaseName.apk"))
    into(rootProject.file("../dist"))
}

chaquopy {
    defaultConfig {
        version = "3.11"
        // 构建机 Python 3.11: 优先本机 Windows 工具链, 回退作者 mac 路径, 再回退 PATH
        val winPy = "D:/WorkSpace/Personal-PC/Music/AndroidToolchain/python311/python.exe"
        val macPy = "/Users/conquer/android-toolchain/python311/bin/python3"
        buildPython(
            when {
                file(winPy).exists() -> winPy
                file(macPy).exists() -> macPy
                else -> "python"
            }
        )
        pip {
            // 装 Python 依赖; 走 TUNA 镜像加速
            options("--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple")
            install("requests")
            install("certifi")
        }
    }
    sourceSets {
        getByName("main") {
            // 复用桌面版纯逻辑 (kuwo / lyrics / paths / util)
            srcDir("../../src")
        }
    }
}

dependencies {
    // 歌单截图 OCR (离线中文+拉丁识别, 用于"从图片导入歌单")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
}

